"""OAuth 2.1 resource-server side of /api/mcp (MCP 2026-07-28 authorization).

Descope is the authorization server: it signs users in, accepts Claude's Client
ID Metadata Document, and issues RS256 JWT access tokens whose ``aud`` is our
resource URL (RFC 8707). This module is the part we own:

- Protected Resource Metadata (RFC 9728), which tells clients where Descope is;
- the ``WWW-Authenticate`` challenge on 401/403;
- access-token checks: signature against Descope's JWKS, ``iss``, ``aud``,
  ``exp``, a subject, and the ``ask`` scope.

OAuth is on when an issuer (MCP_OAUTH_ISSUER, else DESCOPE_ISSUER) and
MCP_RESOURCE_URL are both set.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, FrozenSet, Optional
from urllib.parse import urlsplit

import jwt

from src.config_loader import get_config

WELL_KNOWN = "/.well-known/oauth-protected-resource"
# Asymmetric only: accepting HS* would let anyone who knows the public key mint tokens.
ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "ES256", "ES384"]
LEEWAY_S = 30
_DISCOVERY_TIMEOUT_S = 5
# Descope answers 403 to urllib's default "Python-urllib" agent (seen live).
_HEADERS = {"User-Agent": "care-beacon-mcp/1.0 (+https://care-beacon-health.vercel.app)"}


@dataclass(frozen=True)
class OAuthSettings:
    issuer: str
    resource: str
    scope: str
    jwks_uri: Optional[str] = None
    discovery_url: Optional[str] = None


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    scopes: FrozenSet[str] = field(default_factory=frozenset)
    client_id: Optional[str] = None


class TokenError(Exception):
    """The token is unusable. ``code`` is the RFC 6750 error code."""

    def __init__(self, code: str, description: str):
        super().__init__(description)
        self.code = code
        self.description = description


class AuthUnavailable(Exception):
    """The authorization server's keys can't be fetched: answer 503, not 401."""


def load_oauth_settings() -> Optional[OAuthSettings]:
    """OAuth settings from the environment, or None when OAuth is off."""
    # MCP_OAUTH_ISSUER is the Descope MCP server's own issuer
    # (…/v1/apps/agentic/<project>/<server>); DESCOPE_ISSUER, from the
    # Marketplace install, is the project's and is only the fallback.
    mcp_issuer = (os.getenv("MCP_OAUTH_ISSUER") or "").strip().rstrip("/")
    issuer = mcp_issuer or (os.getenv("DESCOPE_ISSUER") or "").strip().rstrip("/")
    resource = (os.getenv("MCP_RESOURCE_URL") or "").strip().rstrip("/")
    if not issuer or not resource:
        return None
    discovery = issuer + "/.well-known/openid-configuration" if mcp_issuer else (
        (os.getenv("DESCOPE_DISCOVERY_URL") or "").strip() or None
    )
    oauth_config = (get_config().get("mcp", {}) or {}).get("oauth", {}) or {}
    return OAuthSettings(
        issuer=issuer,
        resource=resource,
        scope=str(oauth_config.get("scope", "ask")),
        jwks_uri=(os.getenv("DESCOPE_JWKS_URL") or "").strip() or None,
        discovery_url=discovery,
    )


def metadata_url(resource: str) -> str:
    """RFC 9728 §3.1: insert the well-known path between the host and the resource path."""
    parts = urlsplit(resource)
    return f"{parts.scheme}://{parts.netloc}{WELL_KNOWN}{parts.path.rstrip('/')}"


def protected_resource_metadata(settings: OAuthSettings) -> Dict[str, Any]:
    return {
        "resource": settings.resource,
        "authorization_servers": [settings.issuer],
        "scopes_supported": [settings.scope],
        "bearer_methods_supported": ["header"],
        "resource_name": "Care Beacon",
        "resource_documentation": "https://care-beacon-health.vercel.app",
    }


def www_authenticate(settings: OAuthSettings, *, error: Optional[str] = None) -> str:
    params = []
    if error:
        params.append(f'error="{error}"')
    params.append(f'resource_metadata="{metadata_url(settings.resource)}"')
    params.append(f'scope="{settings.scope}"')
    return "Bearer " + ", ".join(params)


def caller_for_subject(subject: str) -> str:
    """Rate-limit key and trace user id: a pseudonym, as Chat does for owner keys."""
    return "oauth:" + hashlib.sha256(subject.encode("utf-8")).hexdigest()[:32]


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and token.startswith("eyJ")


def _scopes(claims: Dict[str, Any]) -> FrozenSet[str]:
    found = set()
    scope = claims.get("scope")
    if isinstance(scope, str):
        found.update(scope.split())
    for name in ("scp", "permissions"):
        value = claims.get(name)
        if isinstance(value, str):
            found.update(value.split())
        elif isinstance(value, list):
            found.update(str(v) for v in value)
    return frozenset(found)


def _discover_jwks_uri(settings: OAuthSettings) -> str:
    if settings.jwks_uri:
        return settings.jwks_uri
    url = settings.discovery_url or settings.issuer + "/.well-known/openid-configuration"
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_DISCOVERY_TIMEOUT_S) as resp:
            doc = json.load(resp)
    except Exception as e:  # network, HTTP or JSON error
        raise AuthUnavailable(f"discovery failed: {type(e).__name__}") from e
    if str(doc.get("issuer", "")).rstrip("/") != settings.issuer:
        raise AuthUnavailable("discovery issuer does not match DESCOPE_ISSUER")
    if not doc.get("jwks_uri"):
        raise AuthUnavailable("discovery has no jwks_uri")
    return doc["jwks_uri"]


class TokenVerifier:
    """Checks access tokens. ``jwks`` is a PyJWKClient (or a test double)."""

    def __init__(self, settings: OAuthSettings, jwks: Any = None):
        self.settings = settings
        self._jwks = jwks

    def _client(self):
        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(
                _discover_jwks_uri(self.settings),
                cache_keys=True,
                timeout=_DISCOVERY_TIMEOUT_S,
                headers=_HEADERS,
            )
        return self._jwks

    def verify(self, token: str) -> TokenClaims:
        try:
            key = self._client().get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as e:
            raise AuthUnavailable("jwks unreachable") from e
        except jwt.PyJWKClientError as e:  # no matching kid, bad JWKS
            raise TokenError("invalid_token", "unknown signing key") from e
        except jwt.InvalidTokenError as e:  # not a decodable JWT header
            raise TokenError("invalid_token", "malformed token") from e
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                audience=self.settings.resource,
                issuer=self.settings.issuer,
                leeway=LEEWAY_S,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.InvalidTokenError as e:
            raise TokenError("invalid_token", type(e).__name__) from e
        scopes = _scopes(claims)
        if self.settings.scope not in scopes:
            raise TokenError("insufficient_scope", f"the {self.settings.scope} scope is required")
        return TokenClaims(
            subject=str(claims["sub"]),
            scopes=scopes,
            client_id=claims.get("client_id") or claims.get("azp"),
        )


@lru_cache(maxsize=4)
def cached_verifier(settings: OAuthSettings) -> TokenVerifier:
    """One verifier (and so one JWKS cache) per settings, per instance."""
    return TokenVerifier(settings)
