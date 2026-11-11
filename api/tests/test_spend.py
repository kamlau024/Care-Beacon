"""Tests for the chat daily spend cap."""

import pytest
from loguru import logger

from src.caching.stats_store import StatsStore
from src.chat.spend import cap_reached, daily_cap_usd
from tests.test_stats_store import ExplodingRedis, FakeRedis


def _store_with_cost(amount):
    store = StatsStore(FakeRedis())
    store.incr_daily_cost(amount)
    return store


def test_default_cap_is_two_dollars():
    assert daily_cap_usd() == 2.0


def test_cap_reached_at_exact_cap():
    assert cap_reached(_store_with_cost(2.00)) is True


def test_cap_reached_above_cap():
    assert cap_reached(_store_with_cost(5.0)) is True


def test_cap_not_reached_below():
    assert cap_reached(_store_with_cost(1.99)) is False


def test_cap_not_reached_with_no_spend():
    assert cap_reached(StatsStore(FakeRedis())) is False


@pytest.mark.parametrize("client", [None, ExplodingRedis()])
def test_cap_fails_open_when_redis_unavailable(client):
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        assert cap_reached(StatsStore(client)) is False
    finally:
        logger.remove(sink)
    assert any("spend cap" in m.lower() for m in messages)


def test_llm_client_and_embeddings_record_daily_cost():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from src.embeddings.embedding_generator import EmbeddingGenerator
    from src.generation.llm_client import LLMClient

    fake = FakeRedis()
    store = StatsStore(fake)

    llm = LLMClient.__new__(LLMClient)
    llm.stats_store = store
    llm._record_cost(0.3)

    gen = EmbeddingGenerator.__new__(EmbeddingGenerator)
    gen.stats_store = store
    gen.cost_per_1k_tokens = 0.1
    gen.total_tokens_used = 0
    gen.total_cost = 0.0
    gen.model = "m"
    gen.max_retries = 1
    gen.batch_size = 10
    gen.client = MagicMock()
    gen.client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0])], usage=SimpleNamespace(total_tokens=1000)
    )
    gen.embed_text("hi")
    gen.client.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.0], index=0)], usage=SimpleNamespace(total_tokens=1000)
    )
    gen.embed_batch(["hi"])

    assert store.get_daily_cost() == pytest.approx(0.5)
