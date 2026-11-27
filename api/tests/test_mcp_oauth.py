"""OAuth resource-server checks for /api/mcp (plan §4, Phase 2).

Tokens are real RS256 JWTs signed with a throwaway key, so these exercise the
actual signature, issuer, audience, expiry and scope checks.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.mcp_server.oauth import (
    AuthUnavailable,
    OAuthSettings,
    TokenError,
    TokenVerifier,
    caller_for_subject,
    load_oauth_settings,
    looks_like_jwt,
    metadata_url,
    protected_resource_metadata,
    www_authenticate,
)

ISSUER = "https://api.descope.com/v1/apps/Ptest"
RESOURCE = "https://care-beacon-mcp-preview.vercel.app/api/mcp"
SETTINGS = OAuthSettings(issuer=ISSUER, resource=RESOURCE, scope="ask", jwks_uri="https://jwks.example/keys")

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:
    """Stands in for PyJWKClient: hands back the public key for any token."""

    def __init__(self, key=_KEY, fail=False):
        self.key, self.fail = key, fail

    def get_signing_key_from_jwt(self, token):
        if self.fail:
            raise jwt.PyJWKClientConnectionError("jwks unreachable")
        return type("K", (), {"key": self.key.public_key()})()


def token(key=_KEY, alg="RS256", **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": [RESOURCE],
        "sub": "U2abc",
        "exp": now + 600,
        "iat": now,
        "scope": "ask offline_access",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg)


@pytest.fixture
def verifier():
    return TokenVerifier(SETTINGS, jwks=FakeJwks())


# --- verify ------------------------------------------------------------------


def test_a_valid_token_gives_its_subject_and_scopes(verifier):
    claims = verifier.verify(token())
    assert claims.subject == "U2abc"
    assert "ask" in claims.scopes


def test_audience_may_be_a_plain_string(verifier):
    assert verifier.verify(token(aud=RESOURCE)).subject == "U2abc"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 120},  # expired, beyond the leeway
        {"aud": ["https://other.example/api/mcp"]},  # issued for another resource
        {"aud": None},  # no audience at all
        {"iss": "https://evil.example"},  # another issuer
        {"sub": None},  # no subject to rate-limit on
    ],
    ids=["expired", "wrong-aud", "no-aud", "wrong-iss", "no-sub"],
)
def test_bad_claims_are_invalid_token(verifier, overrides):
    with pytest.raises(TokenError) as e:
        verifier.verify(token(**overrides))
    assert e.value.code == "invalid_token"


def test_a_token_signed_by_another_key_is_rejected(verifier):
    with pytest.raises(TokenError) as e:
        verifier.verify(token(key=_OTHER_KEY))
    assert e.value.code == "invalid_token"


def test_a_symmetric_token_is_rejected_even_with_a_matching_secret():
    # alg confusion: never accept HS256 just because the "key" verifies it.
    forged = jwt.encode(
        {"iss": ISSUER, "aud": RESOURCE, "sub": "x", "exp": int(time.time()) + 60, "scope": "ask"},
        "secret-from-somewhere-long-enough-for-hs256",
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        TokenVerifier(SETTINGS, jwks=FakeJwks()).verify(forged)


def test_missing_scope_is_insufficient_scope(verifier):
    with pytest.raises(TokenError) as e:
        verifier.verify(token(scope="offline_access"))
    assert e.value.code == "insufficient_scope"


@pytest.mark.parametrize("claim", [{"scp": ["ask"]}, {"permissions": ["ask"]}])
def test_scope_is_read_from_list_claims_too(verifier, claim):
    assert "ask" in verifier.verify(token(scope=None, **claim)).scopes


def test_unreachable_jwks_is_auth_unavailable_not_a_401():
    with pytest.raises(AuthUnavailable):
        TokenVerifier(SETTINGS, jwks=FakeJwks(fail=True)).verify(token())


# --- metadata and headers ------------------------------------------------------


def test_metadata_url_inserts_the_well_known_path_before_the_resource_path():
    # RFC 9728 §3.1
    assert metadata_url(RESOURCE) == (
        "https://care-beacon-mcp-preview.vercel.app/.well-known/oauth-protected-resource/api/mcp"
    )


def test_protected_resource_metadata():
    assert protected_resource_metadata(SETTINGS) == {
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": ["ask"],
        "bearer_methods_supported": ["header"],
        "resource_name": "Care Beacon",
        "resource_documentation": "https://care-beacon-health.vercel.app",
    }


def test_www_authenticate_points_at_the_metadata_and_scope():
    assert www_authenticate(SETTINGS) == (
        'Bearer resource_metadata="https://care-beacon-mcp-preview.vercel.app'
        '/.well-known/oauth-protected-resource/api/mcp", scope="ask"'
    )


def test_www_authenticate_carries_the_error_code():
    assert www_authenticate(SETTINGS, error="insufficient_scope").startswith(
        'Bearer error="insufficient_scope", resource_metadata='
    )


# --- helpers -------------------------------------------------------------------


def test_caller_is_a_pseudonym_never_the_subject():
    caller = caller_for_subject("U2abc")
    assert caller.startswith("oauth:") and "U2abc" not in caller
    assert caller == caller_for_subject("U2abc") != caller_for_subject("U2abd")


def test_looks_like_jwt():
    assert looks_like_jwt(token())
    assert not looks_like_jwt("plain-static-key_abc123")


def test_settings_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("DESCOPE_ISSUER", ISSUER)
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE + "/")  # trailing slash is normalised
    monkeypatch.setenv("DESCOPE_DISCOVERY_URL", ISSUER + "/.well-known/openid-configuration")
    s = load_oauth_settings()
    assert (s.issuer, s.resource, s.scope) == (ISSUER, RESOURCE, "ask")


@pytest.mark.parametrize("missing", ["DESCOPE_ISSUER", "MCP_RESOURCE_URL"])
def test_oauth_is_off_without_issuer_or_resource(monkeypatch, missing):
    monkeypatch.setenv("DESCOPE_ISSUER", ISSUER)
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.delenv(missing)
    assert load_oauth_settings() is None


# --- talking to Descope ---------------------------------------------------------


def test_discovery_and_jwks_requests_name_a_user_agent(monkeypatch):
    # Seen live: Descope answers 403 to urllib's default "Python-urllib" agent.
    import io
    import json as _json

    import src.mcp_server.oauth as oauth

    seen = {}

    def fake_urlopen(req, timeout):
        seen["discovery_ua"] = req.get_header("User-agent")
        return io.BytesIO(_json.dumps({"issuer": ISSUER, "jwks_uri": "https://jwks.example/k"}).encode())

    class FakeClient:
        def __init__(self, uri, **kwargs):
            seen["jwks_uri"], seen["jwks_headers"] = uri, kwargs.get("headers") or {}

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(oauth.jwt, "PyJWKClient", FakeClient)
    TokenVerifier(OAuthSettings(issuer=ISSUER, resource=RESOURCE, scope="ask"))._client()
    assert seen["discovery_ua"] and "urllib" not in seen["discovery_ua"].lower()
    assert seen["jwks_uri"] == "https://jwks.example/k"
    assert seen["jwks_headers"].get("User-Agent") == seen["discovery_ua"]


def test_the_mcp_server_issuer_overrides_the_project_issuer(monkeypatch):
    # Descope gives each MCP server its own issuer (…/v1/apps/agentic/<project>/<server>);
    # the Marketplace's DESCOPE_ISSUER / DESCOPE_DISCOVERY_URL are the project's.
    agentic = "https://api.descope.com/v1/apps/agentic/Ptest/MSid"
    monkeypatch.setenv("DESCOPE_ISSUER", ISSUER)
    monkeypatch.setenv("DESCOPE_DISCOVERY_URL", ISSUER + "/.well-known/openid-configuration")
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("MCP_OAUTH_ISSUER", agentic + "/")
    s = load_oauth_settings()
    assert s.issuer == agentic
    assert s.discovery_url == agentic + "/.well-known/openid-configuration"
