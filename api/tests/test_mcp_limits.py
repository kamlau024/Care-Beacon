"""Tests for the per-caller MCP rate limiter and settings (plan §4)."""

import pytest
from redis.exceptions import RedisError

from src.mcp_server.limits import McpSettings, RateLimiter, load_settings


class CountingRedis:
    """In-memory INCR/EXPIRE."""

    def __init__(self):
        self.data = {}
        self.ttls = {}

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds


class BrokenRedis:
    def incr(self, key):
        raise RedisError("down")

    def expire(self, key, seconds):
        raise RedisError("down")


def _limiter(client, per_minute=2, per_day=5, now=1_000_000.0):
    return RateLimiter(client, per_minute=per_minute, per_day=per_day, clock=lambda: now)


def test_allows_calls_up_to_the_minute_limit():
    limiter = _limiter(CountingRedis())
    assert limiter.check("kam") is None
    assert limiter.check("kam") is None


def test_the_next_call_in_the_minute_is_refused_with_seconds_to_wait():
    limiter = _limiter(CountingRedis(), now=60 * 16_667 + 20.0)  # 20 s into a minute
    limiter.check("kam")
    limiter.check("kam")
    assert limiter.check("kam") == 40


def test_callers_have_separate_buckets():
    limiter = _limiter(CountingRedis())
    limiter.check("kam")
    limiter.check("kam")
    assert limiter.check("eval-harness") is None


def test_the_daily_limit_applies_across_minutes():
    client = CountingRedis()
    for minute in range(5):
        assert _limiter(client, per_minute=10, per_day=5, now=minute * 60.0).check("kam") is None
    refused = _limiter(client, per_minute=10, per_day=5, now=5 * 60.0).check("kam")
    assert refused == 86_400 - 5 * 60


def test_keys_expire():
    client = CountingRedis()
    _limiter(client).check("kam")
    assert sorted(client.ttls.values()) == [120, 172_800]


@pytest.mark.parametrize("client", [None, BrokenRedis()])
def test_fails_closed_without_redis(client):
    assert _limiter(client).check("kam") == 60


def test_settings_default_from_config(monkeypatch):
    for v in ("MCP_DAILY_SPEND_CAP_USD", "MCP_RATE_LIMIT_PER_MIN", "VERCEL_ENV"):
        monkeypatch.delenv(v, raising=False)
    s = load_settings()
    assert s == McpSettings(daily_spend_cap_usd=2.0, per_minute=10, per_day=50)


def test_env_overrides_apply_outside_production(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setenv("MCP_DAILY_SPEND_CAP_USD", "0")
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MIN", "1")
    s = load_settings()
    assert s.daily_spend_cap_usd == 0.0
    assert s.per_minute == 1


def test_env_overrides_are_ignored_in_production(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("MCP_DAILY_SPEND_CAP_USD", "1000")
    monkeypatch.setenv("MCP_RATE_LIMIT_PER_MIN", "1000")
    s = load_settings()
    assert s.daily_spend_cap_usd == 2.0
    assert s.per_minute == 10
