"""Tests for the Redis-backed statistics store."""

import pytest

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
    """Redis down must degrade to zeros, never raise into the request path."""
    store = StatsStore(None)
    store.incr("llm_calls", 1)
    store.incr_float("llm_cost", 1.5)
    store.reset()
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

    with patch("src.generation.llm_client.OpenAI"):
        client = LLMClient(api_key="test-key", stats_store=store)

    stats = client.get_stats()
    assert stats["total_calls"] == 10
    assert stats["total_cost"] == pytest.approx(0.42)
