"""The Care Beacon MCP server: one tool, ask_care_beacon, served at /api/mcp.

Shape (plan §2, lessons from the Phase 0 spike):

- Stateless Streamable HTTP with JSON responses: one POST, one JSON reply.
- `McpGuard` runs before the SDK: POST only, Origin, static bearer key.
- The SDK app is rebuilt per FastAPI lifespan (`mcp_lifespan`), because its
  session manager's run() works only once per instance.
- DNS-rebinding protection is turned off explicitly. With no
  transport_security, the SDK's default host="127.0.0.1" enables it with a
  localhost-only Host list and every deployed request gets 421.
"""

# No `from __future__ import annotations`: the SDK reads the tool's type hints
# at registration, and the sources enum is built locally in build_server().
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, Dict, List, Literal, Optional

import anyio
from loguru import logger
from mcp.server.caching import CacheHint
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field, ValidationError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.api.ask_service import AskOutcome, InvalidSources, answer_question
from src.api.filters import configured_sources
from src.api.models import QuestionRequest
from src.caching.stats_store import spend_channel
from src.config_loader import get_config
from src.mcp_server.auth import authenticate, parse_keys
from src.mcp_server.format import build_citations, render_markdown, renumber
from src.mcp_server.oauth import (
    AuthUnavailable,
    OAuthSettings,
    WELL_KNOWN,
    TokenError,
    cached_verifier,
    caller_for_subject,
    load_oauth_settings,
    looks_like_jwt,
    protected_resource_metadata,
    www_authenticate,
)
from src.mcp_server.limits import (
    MCP_CHANNEL,
    RateLimiter,
    load_settings,
    mcp_cap_reached,
)
from src.mcp_server.schemas import AnswerMeta, AppliedSettings, CareBeaconAnswer, ErrorInfo
from src.observability.tracing import flush

MCP_PATH = "/api/mcp"
TOOL_NAME = "ask_care_beacon"

# Requests without an Origin are server-to-server (Claude's connector sends
# none; checked in Phase 0). Browser origins must be ours.
ALLOWED_ORIGINS = frozenset({"https://care-beacon-health.vercel.app"})

# Under the function's 60 s maxDuration, so a slow answer becomes a tool error
# instead of a platform timeout.
ANSWER_TIMEOUT_S = 50

TOOL_DESCRIPTION = (
    "Answer a question about cancer: types, symptoms, diagnosis, treatment, side effects, "
    "coping and survivorship. The answer is drawn from patient-education pages from "
    "BC Cancer, the Canadian Cancer Society and Cleveland Clinic. Returns an answer "
    "grounded only in those pages, with numbered citations (title, section, URL) and a "
    "medical disclaimer. Use it for general medical information, not for personal "
    "diagnosis or treatment decisions: Care Beacon will refer those to a healthcare "
    "provider. Each call takes about 10-25 seconds. Ask one self-contained question per "
    "call, and include any context from earlier in the conversation in the question itself."
)

INSTRUCTIONS = (
    "Care Beacon answers general cancer questions from trusted patient-education sources, "
    "with citations. Call ask_care_beacon once per self-contained question. Show the "
    "citations and the disclaimer to the user. Never present an answer as personal "
    "medical advice."
)


# --- results -----------------------------------------------------------------


def error_result(code: str, message: str, **details: Any) -> CallToolResult:
    """An isError tool result with a readable message and a stable error object."""
    info = ErrorInfo(code=code, message=message, **details)
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structured_content={"error": info.model_dump(exclude_none=True)},
        is_error=True,
    )


def answer_result(answer: CareBeaconAnswer) -> CallToolResult:
    """Readable Markdown first, then the serialized structured content (spec SHOULD)."""
    data = answer.model_dump(mode="json")
    return CallToolResult(
        content=[
            TextContent(type="text", text=render_markdown(answer)),
            TextContent(type="text", text=json.dumps(data, ensure_ascii=False)),
        ],
        structured_content=data,
    )


def _invalid_arguments(exc: ValidationError) -> CallToolResult:
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err["loc"]) or None
    if field and field.startswith("sources"):
        allowed = ", ".join(configured_sources())
        message = f"Invalid argument 'sources': each entry must be one of: {allowed}."
    else:
        message = f"Invalid argument '{field}': {err['msg']}."
    return error_result("invalid_arguments", message, field=field)


# --- server ------------------------------------------------------------------


class CareBeaconMCP(MCPServer):
    """MCPServer whose argument errors use Care Beacon's invalid_arguments shape."""

    async def call_tool(self, name, arguments, context=None):  # type: ignore[override]
        tool = self._tool_manager.get_tool(name)
        if tool is not None:
            allowed = set(tool.parameters.get("properties", {}))
            unknown = sorted(set(arguments or {}) - allowed)
            if unknown:
                return error_result(
                    "invalid_arguments",
                    f"Unknown argument(s): {', '.join(unknown)}. "
                    f"Allowed: {', '.join(sorted(allowed))}.",
                    field=unknown[0],
                )
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            # The SDK reports schema violations as ToolError(cause=ValidationError),
            # whose text is pydantic's (with a docs URL). Replace it with ours.
            if isinstance(exc.__cause__, ValidationError):
                return _invalid_arguments(exc.__cause__)
            raise


def _caller(ctx: Context) -> str:
    """The authenticated caller McpGuard stored on the request."""
    request = ctx.request_context.request
    return (getattr(request, "scope", None) or {}).get("state", {}).get("mcp_caller", "unknown")


def _client(ctx: Context) -> Optional[str]:
    """`name/version` from the request's clientInfo, if the client sent one."""
    rc = ctx.request_context
    try:
        params = rc.session.client_params
        info = params.client_info if params is not None else None
        if info is not None:
            return f"{info.name}/{info.version}"
        raw = (rc.meta or {}).get("io.modelcontextprotocol/clientInfo") or {}
        if isinstance(raw, dict) and raw.get("name"):
            return f"{raw['name']}/{raw.get('version', '?')}"
    except Exception:
        pass
    return None


def _get_generator() -> Any:
    # Imported here: src.api.main imports this module. Tests patch the same
    # function the /ask tests patch.
    from src.api import main

    return main.get_answer_generator()


def build_server() -> CareBeaconMCP:
    """Construct the server and register ask_care_beacon."""
    sources = configured_sources()
    SourceName = Literal[tuple(sources)]  # type: ignore[valid-type]
    default_min_similarity = float(get_config().get("mcp.min_similarity_default", 0.5))

    server = CareBeaconMCP(
        "care-beacon",
        title="Care Beacon",
        instructions=INSTRUCTIONS,
        website_url="https://care-beacon-health.vercel.app",
        cache_hints={"tools/list": CacheHint(ttl_ms=3_600_000, scope="public")},
        subscriptions=False,
    )

    @server.tool(
        name=TOOL_NAME,
        title="Ask Care Beacon",
        description=TOOL_DESCRIPTION,
        annotations=ToolAnnotations(
            title="Ask Care Beacon",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def ask_care_beacon(
        question: Annotated[
            str,
            Field(
                min_length=3,
                max_length=500,
                description=(
                    "One self-contained question in plain language. Resolve pronouns "
                    "from earlier turns before asking."
                ),
            ),
        ],
        ctx: Context,
        sources: Annotated[
            Optional[List[SourceName]],
            Field(
                min_length=1,
                description="Only use these sources. Omit to use all three (the app default).",
            ),
        ] = None,
        min_similarity: Annotated[
            float,
            Field(
                ge=0,
                le=1,
                description=(
                    "Minimum relevance (0-1) for a source to be used. Higher means fewer "
                    "but closer sources. Default 0.5, the same as the Search page."
                ),
            ),
        ] = default_min_similarity,
        max_results: Annotated[
            int,
            Field(ge=1, le=10, description="Maximum number of source passages to answer from."),
        ] = 5,
        include_source_text: Annotated[
            bool,
            Field(
                description=(
                    "Also return the full text of each cited passage, so you can verify or "
                    "quote it. Makes the result much larger."
                )
            ),
        ] = False,
    ) -> Annotated[CallToolResult, CareBeaconAnswer]:
        return await run_ask(
            ctx,
            question=question,
            sources=list(sources) if sources else None,
            min_similarity=min_similarity,
            max_results=max_results,
            include_source_text=include_source_text,
        )

    # Publish the rule CareBeaconMCP.call_tool enforces.
    server._tool_manager.get_tool(TOOL_NAME).parameters["additionalProperties"] = False

    # MCPServer always registers prompt and resource handlers, and capabilities
    # are derived from registered handlers, so discover advertised prompts and
    # resources we don't have. Claude then spent a call on each (Phase 0).
    # Private API; pinned by test_discover_advertises_only_tools.
    for method in (
        "prompts/list",
        "prompts/get",
        "resources/list",
        "resources/read",
        "resources/templates/list",
    ):
        server._lowlevel_server._request_handlers.pop(method, None)

    # The SDK wraps every request in its own OpenTelemetry span. Once Langfuse
    # sets the global tracer, mcp_ask nests under it, but that span ends after
    # run_ask's flush and is lost when the instance freezes: mcp_ask is left with
    # a missing parent and the root-only live evaluators skip it. mcp_ask is the
    # root, as ask is for Search. Pinned by test_mcp_ask_is_not_nested_under_an_sdk_span.
    server._lowlevel_server.middleware = [
        m for m in server._lowlevel_server.middleware if type(m).__name__ != "OpenTelemetryMiddleware"
    ]
    return server


async def run_ask(
    ctx: Context,
    *,
    question: str,
    sources: Optional[List[str]],
    min_similarity: float,
    max_results: int,
    include_source_text: bool,
) -> CallToolResult:
    """Limits, then the shared answer pipeline, then formatting."""
    caller = _caller(ctx)
    settings = load_settings()
    generator = _get_generator()
    stats_store = generator.cache.stats_store

    retry_after = RateLimiter(
        stats_store.client, per_minute=settings.per_minute, per_day=settings.per_day
    ).check(caller)
    if retry_after is not None:
        return error_result(
            "rate_limited",
            f"Rate limit reached; try again in {retry_after} seconds. Do not retry immediately.",
            retry_after_s=retry_after,
        )
    if mcp_cap_reached(stats_store, cap_usd=settings.daily_spend_cap_usd):
        return error_result(
            "daily_limit_reached",
            "Care Beacon's daily budget is used up; it resets at 00:00 UTC.",
            resets_at=_next_utc_midnight(),
        )

    applied = AppliedSettings(
        sources=sources or configured_sources(),
        min_similarity=min_similarity,
        max_results=max_results,
    )
    req = QuestionRequest(
        question=question,
        source=sources,
        max_results=max_results,
        min_similarity=min_similarity,
        include_full_text=include_source_text,
    )
    formatted: Dict[str, Any] = {}

    def annotate(outcome: AskOutcome) -> Dict[str, Any]:
        text, unmatched = renumber(outcome.response.answer, outcome.response.sources)
        formatted.update(text=text, unmatched=unmatched)
        return {"unmatched_markers": unmatched, "settings_applied": applied.model_dump()}

    started = time.perf_counter()

    def run() -> AskOutcome:
        try:
            return _answer()
        finally:
            # After the root span has closed: on Vercel the instance can freeze once
            # the reply is sent, losing whatever the Langfuse SDK still buffers.
            flush()

    def _answer() -> AskOutcome:
        return answer_question(
            req,
            generator,
            trace_name="mcp_ask",
            endpoint=MCP_PATH,
            # The tool promises at most max_results sources; Search shows all above the threshold.
            cap_results=True,
            extra_metadata={
                "channel": MCP_CHANNEL,
                "mcp": {
                    "client": _client(ctx),
                    "protocol_version": ctx.protocol_version,
                    "caller": caller,  # key name, or oauth:<sha256 of sub>
                },
                "arguments": {
                    "sources": sources,
                    "min_similarity": min_similarity,
                    "max_results": max_results,
                    "include_source_text": include_source_text,
                },
            },
            user_id=caller,
            tags=["mcp"],
            annotate=annotate,
        )

    try:
        with spend_channel(MCP_CHANNEL), anyio.fail_after(ANSWER_TIMEOUT_S):
            outcome = await anyio.to_thread.run_sync(run, abandon_on_cancel=True)
    except InvalidSources as e:
        return error_result("invalid_arguments", str(e), field="sources")
    except TimeoutError:
        logger.warning("ask_care_beacon timed out after {}s", ANSWER_TIMEOUT_S)
        return error_result(
            "timeout", "Care Beacon took too long to answer. Try again, or ask a narrower question."
        )
    except Exception:
        logger.exception("ask_care_beacon failed")
        return error_result(
            "upstream_unavailable", "Care Beacon is temporarily unavailable. Try again later."
        )

    response = outcome.response
    answer = CareBeaconAnswer(
        answer=formatted.get("text", response.answer),
        answered=bool(response.sources),
        citations=build_citations(response.sources, include_text=include_source_text),
        disclaimer=response.disclaimer or "",
        settings=applied,
        meta=AnswerMeta(
            model=response.model,
            cached=bool(response.metadata.get("cached")),
            cost_usd=float(response.metadata.get("cost") or 0.0),
            duration_ms=int((time.perf_counter() - started) * 1000),
            trace_id=outcome.trace_id,
        ),
    )
    return answer_result(answer)


def _next_utc_midnight() -> str:
    from datetime import datetime, timedelta, timezone

    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    return f"{tomorrow.isoformat()}T00:00:00Z"


# --- HTTP layer ----------------------------------------------------------------

server = build_server()
_current_endpoint: Optional[ASGIApp] = None


@asynccontextmanager
async def mcp_lifespan() -> AsyncIterator[None]:
    """Build the SDK's HTTP app and run its session manager for one app lifespan."""
    global _current_endpoint
    sdk_app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    async with server.session_manager.run():
        _current_endpoint = sdk_app.routes[0].endpoint
        try:
            yield
        finally:
            _current_endpoint = None


_LOGGED_HEADERS = ("origin", "user-agent", "mcp-protocol-version", "mcp-method", "mcp-name")

# Once OAuth is on, static keys are for automation only (plan §4).
STATIC_KEY_NAMES_WITH_OAUTH = frozenset({"eval-harness", "smoke"})

# Patched in tests; one verifier (and JWKS cache) per settings per instance.
get_token_verifier = cached_verifier


def _bearer(authorization: Optional[str]) -> Optional[str]:
    scheme, _, token = (authorization or "").strip().partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and token else None


async def _authorize(
    authorization: Optional[str], oauth: Optional[OAuthSettings], keys: Dict[str, str]
):
    """Return (caller, None) when allowed, else (None, (status, body, headers, reason))."""
    challenge = {"WWW-Authenticate": www_authenticate(oauth) if oauth else "Bearer"}
    token = _bearer(authorization)
    if token is None:
        reason = "missing" if not authorization else "not_bearer"
        return None, (401, {"error": "unauthorized"}, challenge, reason)
    if oauth is not None and looks_like_jwt(token):
        try:
            claims = await anyio.to_thread.run_sync(get_token_verifier(oauth).verify, token)
        except AuthUnavailable as e:
            logger.warning("mcp auth unavailable: {}", e)
            return None, (503, {"error": "auth_unavailable"}, None, "auth_unavailable")
        except TokenError as e:
            status = 403 if e.code == "insufficient_scope" else 401
            headers = {"WWW-Authenticate": www_authenticate(oauth, error=e.code)}
            return None, (status, {"error": e.code}, headers, f"{e.code}: {e.description}")
        return caller_for_subject(claims.subject), None
    name = authenticate(authorization, keys)
    if name is None:
        return None, (401, {"error": "unauthorized"}, challenge, "unknown_key")
    if oauth is not None and name not in STATIC_KEY_NAMES_WITH_OAUTH:
        return None, (401, {"error": "unauthorized"}, challenge, f"static_key_not_allowed:{name}")
    return name, None


PRM_PATHS = (WELL_KNOWN + MCP_PATH, WELL_KNOWN)


async def protected_resource_metadata_endpoint(request: Any) -> JSONResponse:
    """GET /.well-known/oauth-protected-resource[/api/mcp] (RFC 9728). Public."""
    oauth = load_oauth_settings()
    if oauth is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(
        protected_resource_metadata(oauth), headers={"Cache-Control": "public, max-age=300"}
    )


class McpGuard:
    """Checks every /api/mcp request before the SDK sees it."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        logger.info(
            "mcp request method={} {}",
            scope["method"],
            {h: headers[h] for h in _LOGGED_HEADERS if h in headers},
        )

        async def reply(status: int, body: Dict[str, Any], extra: Optional[Dict[str, str]] = None):
            await JSONResponse(body, status_code=status, headers=extra)(scope, receive, send)

        # POST only: a GET without MCP-Protocol-Version would open a legacy SSE
        # stream and hold the function until maxDuration.
        if scope["method"] != "POST":
            return await reply(405, {"error": "method_not_allowed"}, {"Allow": "POST"})
        origin = headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return await reply(403, {"error": "forbidden_origin"})
        oauth = load_oauth_settings()
        keys = parse_keys(os.getenv("MCP_API_KEYS"))
        if oauth is None and not keys:
            # Fail closed: no way to authenticate means the endpoint is off.
            return await reply(503, {"error": "mcp_disabled"})
        caller, refusal = await _authorize(headers.get("authorization"), oauth, keys)
        if refusal is not None:
            status, body, extra, reason = refusal
            # The reason, never the credential (Phase 1 finding).
            logger.info("mcp auth refused status={} reason={}", status, reason)
            return await reply(status, body, extra)
        if _current_endpoint is None:
            return await reply(503, {"error": "mcp_not_started"})
        scope.setdefault("state", {})["mcp_caller"] = caller
        await _current_endpoint(scope, receive, send)


mcp_asgi: ASGIApp = McpGuard()
