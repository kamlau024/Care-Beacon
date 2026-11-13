"""Tests for the Redis-backed statistics store."""

from datetime import date

import pytest
from redis.exceptions import RedisError

from src.caching.stats_store import StatsStore


class FakeRedis:
    """Minimal in-memory stand-in for the Redis commands StatsStore uses."""

    def __init__(self):
        self.data = {}

    def hincrby(self, name, key, amount):
        self.data.setdefault(name, {})
        self.data[name][key] = int(self.data[name].get(key, 0)) + amount

    def hincrbyfloat(self, name, key, amount):
        self.data.setdefault(name, {})
        self.data[name][key] = float(self.data[name].get(key, 0)) + amount

    def hgetall(self, name):
        return {k: str(v) for k, v in self.data.get(name, {}).items()}

    def delete(self, name):
        self.data.pop(name, None)

    # String-key operations (daily cost counter)
    def incrbyfloat(self, name, amount):
        self.data[name] = float(self.data.get(name, 0)) + amount
        return self.data[name]

    def expire(self, name, seconds):
        self.ttls = getattr(self, "ttls", {})
        self.ttls[name] = seconds

    def ttl(self, name):
        return getattr(self, "ttls", {}).get(name, -1)

    def get(self, name):
        value = self.data.get(name)
        return None if value is None else str(value)


class ExplodingRedis:
    """Redis stand-in whose every command raises, simulating an outage mid-call.

    This is the fake that actually exercises the `except RedisError` branches —
    FakeRedis above never fails, so it cannot prove the no-raise guarantee.
    """

    def hincrby(self, name, key, amount):
        raise RedisError("connection lost")

    def hincrbyfloat(self, name, key, amount):
        raise RedisError("connection lost")

    def hgetall(self, name):
        raise RedisError("connection lost")

    def delete(self, name):
        raise RedisError("connection lost")

    def incrbyfloat(self, name, amount):
        raise RedisError("connection lost")

    def expire(self, name, seconds):
        raise RedisError("connection lost")

    def get(self, name):
        raise RedisError("connection lost")


class MalformedValueRedis:
    """Redis stand-in whose hash contains a non-numeric value.

    Nothing in this codebase writes non-numeric values today, but get_all()'s
    contract is "never raise", so a corrupted/foreign value must degrade
    gracefully rather than blow up with an uncaught ValueError.
    """

    def hgetall(self, name):
        return {"llm_cost": "not-a-number"}


def test_counters_accumulate_across_separate_instances():
    """The whole point: two instances sharing Redis must see one total."""
    shared = FakeRedis()

    StatsStore(shared).incr("llm_calls", 3)
    StatsStore(shared).incr("llm_calls", 2)

    assert StatsStore(shared).get_all()["llm_calls"] == 5


def test_float_and_int_counters_coexist():
    store = StatsStore(FakeRedis())
    store.incr("llm_calls", 2)
    store.incr_float("llm_cost", 0.0025)

    result = store.get_all()
    assert result["llm_calls"] == 2.0
    assert result["llm_cost"] == pytest.approx(0.0025)


def test_missing_field_reads_as_zero():
    assert StatsStore(FakeRedis()).get_all().get("llm_cost", 0.0) == 0.0


def test_reset_clears_every_field():
    store = StatsStore(FakeRedis())
    store.incr("llm_calls", 7)
    store.reset()
    assert store.get_all() == {}


def test_none_client_is_a_silent_no_op():
    """StatsStore(None) takes the early-return branch on every method and never raises.

    This only covers "no client configured" (client is None). It says nothing
    about Redis raising mid-call on a configured client — that's covered by
    test_exploding_redis_is_silent_and_degrades_to_empty below.
    """
    store = StatsStore(None)
    store.incr("llm_calls", 1)
    store.incr_float("llm_cost", 1.5)
    store.reset()
    assert store.get_all() == {}


def test_exploding_redis_is_silent_and_degrades_to_empty():
    """Redis down must degrade to zeros, never raise into the request path.

    Unlike the None-client case above, this drives a configured client whose
    every command raises RedisError mid-call — the actual outage scenario the
    `except RedisError` branches exist for.
    """
    store = StatsStore(ExplodingRedis())

    store.incr("llm_calls", 1)
    store.incr_float("llm_cost", 1.5)
    store.reset()

    assert store.get_all() == {}


def test_malformed_value_in_hash_does_not_raise():
    """A non-numeric hash value must degrade to empty stats, not raise ValueError."""
    store = StatsStore(MalformedValueRedis())
    assert store.get_all() == {}


def test_llm_client_reports_persisted_totals_not_instance_totals():
    """A fresh client on the same Redis must report the accumulated total."""
    from unittest.mock import patch
    from src.caching.stats_store import StatsStore
    from src.generation.llm_client import LLMClient

    shared = FakeRedis()
    store = StatsStore(shared)
    store.incr("llm_calls", 10)
    store.incr_float("llm_cost", 0.42)

    with patch("src.generation.llm_client.get_openai_client"):
        client = LLMClient(api_key="test-key", stats_store=store)

    stats = client.get_stats()
    assert stats["total_calls"] == 10
    assert stats["total_cost"] == pytest.approx(0.42)


def test_daily_cost_uses_utc_date_key_and_ttl():
    fake = FakeRedis()
    store = StatsStore(fake)

    store.incr_daily_cost(0.5, day=date(2026, 11, 11))
    store.incr_daily_cost(0.25, day=date(2026, 11, 11))

    assert fake.data["care_beacon:cost:2026-11-11"] == pytest.approx(0.75)
    assert fake.ttl("care_beacon:cost:2026-11-11") == 172800
    assert store.get_daily_cost(date(2026, 11, 11)) == pytest.approx(0.75)


def test_daily_cost_defaults_to_utc_today(monkeypatch):
    from datetime import datetime, timezone

    fake = FakeRedis()
    StatsStore(fake).incr_daily_cost(1.0)

    today = datetime.now(timezone.utc).date().isoformat()
    assert f"care_beacon:cost:{today}" in fake.data


def test_get_daily_cost_missing_key_is_zero_not_none():
    assert StatsStore(FakeRedis()).get_daily_cost(date(2026, 1, 1)) == 0.0


def test_daily_cost_unavailable_is_none_and_never_raises():
    assert StatsStore(None).get_daily_cost() is None
    StatsStore(None).incr_daily_cost(1.0)

    store = StatsStore(ExplodingRedis())
    store.incr_daily_cost(1.0)
    assert store.get_daily_cost() is None
