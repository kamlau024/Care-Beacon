"""Tests for static MCP keys (development and evals; plan §4)."""

import hashlib

import pytest

from src.mcp_server.auth import authenticate, make_key, parse_keys


def _sha(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


KEYS = f"claude-desktop-kam:{_sha('secret-one')},eval-harness:{_sha('secret-two')}"


def test_parse_keys_reads_name_hash_pairs():
    assert parse_keys(KEYS) == {
        "claude-desktop-kam": _sha("secret-one"),
        "eval-harness": _sha("secret-two"),
    }


@pytest.mark.parametrize("raw", [None, "", "  ", ",,"])
def test_parse_keys_empty_means_no_keys(raw):
    assert parse_keys(raw) == {}


def test_parse_keys_skips_malformed_entries():
    assert parse_keys(f"nohash, :{_sha('x')}, ok:{_sha('y')}, bad:nothex") == {"ok": _sha("y")}


def test_authenticate_returns_the_key_name():
    keys = parse_keys(KEYS)
    assert authenticate("Bearer secret-two", keys) == "eval-harness"
    assert authenticate("bearer secret-one", keys) == "claude-desktop-kam"


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer ", "Basic secret-one", "secret-one", "Bearer wrong"])
def test_authenticate_rejects_anything_else(header):
    assert authenticate(header, parse_keys(KEYS)) is None


def test_authenticate_with_no_keys_configured_rejects():
    assert authenticate("Bearer secret-one", {}) is None


def test_make_key_line_authenticates_the_raw_key():
    raw, line = make_key("smoke")
    assert len(raw) >= 43  # 32 random bytes, url-safe base64
    assert line.startswith("smoke:")
    assert authenticate(f"Bearer {raw}", parse_keys(line)) == "smoke"


@pytest.mark.parametrize("name", ["", "has space", "a:b", "a,b"])
def test_make_key_rejects_names_that_would_break_the_env_line(name):
    with pytest.raises(ValueError):
        make_key(name)
