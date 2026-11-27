"""Tests for the separate MCP daily spend counter and cap (plan §3.3)."""

import anyio
import pytest

from src.caching.stats_store import StatsStore, spend_channel
from src.chat.spend import cap_reached as chat_cap_reached
from src.mcp_server.limits import mcp_cap_reached
from tests.test_stats_store import ExplodingRedis, FakeRedis


def test_spend_outside_a_channel_counts_only_toward_the_total():
    store = StatsStore(FakeRedis())
    store.incr_daily_cost(0.5)
    assert store.get_daily_cost() == 0.5
    assert store.get_daily_cost(channel="mcp") == 0.0


def test_spend_inside_the_mcp_channel_counts_toward_both():
    store = StatsStore(FakeRedis())
    with spend_channel("mcp"):
        store.incr_daily_cost(0.25)
    store.incr_daily_cost(0.5)
    assert store.get_daily_cost() == 0.75
    assert store.get_daily_cost(channel="mcp") == 0.25


def test_the_channel_follows_work_run_in_a_worker_thread():
    # The tool runs the synchronous generator with anyio.to_thread.run_sync.
    store = StatsStore(FakeRedis())

    async def main():
        with spend_channel("mcp"):
            await anyio.to_thread.run_sync(store.incr_daily_cost, 0.1)

    anyio.run(main)
    assert store.get_daily_cost(channel="mcp") == pytest.approx(0.1)


def test_mcp_spend_does_not_close_chat():
    store = StatsStore(FakeRedis())
    with spend_channel("mcp"):
        store.incr_daily_cost(1.9)
    store.incr_daily_cost(0.5)  # Chat and Search
    assert chat_cap_reached(store) is False


def test_chat_spend_still_closes_chat():
    store = StatsStore(FakeRedis())
    store.incr_daily_cost(2.0)
    assert chat_cap_reached(store) is True


def test_chat_spend_does_not_close_mcp():
    store = StatsStore(FakeRedis())
    store.incr_daily_cost(5.0)
    assert mcp_cap_reached(store, cap_usd=2.0) is False


def test_mcp_cap_reached_at_the_cap():
    store = StatsStore(FakeRedis())
    with spend_channel("mcp"):
        store.incr_daily_cost(2.0)
    assert mcp_cap_reached(store, cap_usd=2.0) is True


@pytest.mark.parametrize("client", [None, ExplodingRedis()])
def test_mcp_cap_fails_closed_when_the_counter_is_unreadable(client):
    assert mcp_cap_reached(StatsStore(client), cap_usd=2.0) is True
