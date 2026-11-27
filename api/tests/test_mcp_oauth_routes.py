"""Contract tests for /api/mcp with OAuth on: the real app, tokens signed locally.

Covers the OAuth rows of the plan's E5 table: no token, expired, wrong
audience or issuer, missing scope, an unreachable JWKS, the static-key fallback
(eval-harness / smoke only), and the Protected Resource Metadata routes.
"""

import hashlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import src.mcp_server.server as server
from src.api.main import app
from src.mcp_server.oauth import TokenVerifier
from tests.test_mcp_oauth import ISSUER, RESOURCE, SETTINGS, FakeJwks, token
from tests.test_mcp_server import call, generator, redis_client, rpc  # noqa: F401 (fixtures)

SMOKE_KEY = "smoke-key-456"
OTHER_KEY = "desktop-key-789"
KEYS = ",".join([
    f"smoke:{hashlib.sha256(SMOKE_KEY.encode()).hexdigest()}",
    f"claude-desktop-kam:{hashlib.sha256(OTHER_KEY.encode()).hexdigest()}",
])
PRM_PATHS = ["/.well-known/oauth-protected-resource/api/mcp", "/.well-known/oauth-protected-resource"]


@pytest.fixture
def jwks():
    return FakeJwks()


@pytest.fixture
def oauth_client(monkeypatch, generator, redis_client, jwks):  # noqa: F811
    monkeypatch.setenv("MCP_API_KEYS", KEYS)
    monkeypatch.setenv("DESCOPE_ISSUER", ISSUER)
    monkeypatch.setenv("MCP_RESOURCE_URL", RESOURCE)
    for var in ("MCP_DAILY_SPEND_CAP_USD", "MCP_RATE_LIMIT_PER_MIN", "VERCEL_ENV", "MCP_OAUTH_ISSUER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(server, "get_token_verifier", lambda settings: TokenVerifier(SETTINGS, jwks=jwks))
    with patch("src.api.main.get_answer_generator", return_value=generator):
        with TestClient(app) as c:
            yield c


QUESTION = {"question": "Why am I so tired?"}


def test_no_token_is_401_pointing_at_the_metadata(oauth_client):
    r = rpc(oauth_client, "tools/list", key=None)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == (
        'Bearer resource_metadata="https://care-beacon-mcp-preview.vercel.app'
        '/.well-known/oauth-protected-resource/api/mcp", scope="ask"'
    )


def test_a_valid_token_calls_the_tool(oauth_client):
    result = call(oauth_client, QUESTION, key=token())
    assert result["isError"] is False


def test_the_caller_is_the_hashed_subject(oauth_client, redis_client, generator):  # noqa: F811
    call(oauth_client, QUESTION, key=token(sub="U2secret"))
    limiter_keys = [k for k in redis_client.data if ":rl:" in k]
    assert limiter_keys and all("oauth:" in k and "U2secret" not in k for k in limiter_keys)


@pytest.mark.parametrize(
    "overrides",
    [{"exp": 1}, {"aud": ["https://other.example/api/mcp"]}, {"iss": "https://evil.example"}],
    ids=["expired", "wrong-aud", "wrong-iss"],
)
def test_a_bad_token_is_401_invalid_token(oauth_client, generator, overrides):  # noqa: F811
    r = rpc(oauth_client, "tools/list", key=token(**overrides))
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith('Bearer error="invalid_token", resource_metadata=')
    generator.generate_answer.assert_not_called()


def test_missing_scope_is_403_insufficient_scope(oauth_client):
    r = rpc(oauth_client, "tools/list", key=token(scope="offline_access"))
    assert r.status_code == 403
    assert r.headers["www-authenticate"].startswith('Bearer error="insufficient_scope"')


def test_unreachable_jwks_is_503(oauth_client, jwks):
    jwks.fail = True
    r = rpc(oauth_client, "tools/list", key=token())
    assert r.status_code == 503
    assert r.json() == {"error": "auth_unavailable"}


def test_smoke_static_key_still_works(oauth_client):
    assert rpc(oauth_client, "tools/list", key=SMOKE_KEY).status_code == 200


def test_other_static_keys_are_refused_once_oauth_is_on(oauth_client):
    assert rpc(oauth_client, "tools/list", key=OTHER_KEY).status_code == 401


def test_oauth_alone_is_enough_without_static_keys(oauth_client, monkeypatch):
    monkeypatch.delenv("MCP_API_KEYS")
    assert rpc(oauth_client, "tools/list", key=token()).status_code == 200


@pytest.mark.parametrize("path", PRM_PATHS)
def test_protected_resource_metadata_is_public(oauth_client, path):
    r = oauth_client.get(path)
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == RESOURCE
    assert body["authorization_servers"] == [ISSUER]
    assert body["scopes_supported"] == ["ask"]


@pytest.mark.parametrize("path", PRM_PATHS)
def test_no_metadata_when_oauth_is_off(oauth_client, monkeypatch, path):
    monkeypatch.delenv("DESCOPE_ISSUER")
    assert oauth_client.get(path).status_code == 404
