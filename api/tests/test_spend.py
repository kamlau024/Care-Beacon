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


def test_answer_generator_reranker_records_daily_cost():
    """The rerank LLM call must count toward the daily spend cap."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from src.generation.answer_generator import AnswerGenerator
    from src.storage.models import RetrievalResult

    store = StatsStore(FakeRedis())
    cache = MagicMock()
    cache.stats_store = store

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="[1, 2]"))],
        usage=SimpleNamespace(prompt_tokens=100000, completion_tokens=0, total_tokens=100000),
    )

    with patch("src.generation.llm_client.get_openai_client", return_value=fake_openai), \
         patch("src.retrieval.retrieval_engine.create_vector_database", return_value=MagicMock()), \
         patch("src.generation.answer_generator.EmbeddingGenerator", return_value=MagicMock()), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        generator = AnswerGenerator(cache=cache)

    reranker = generator.retrieval_engine.reranker
    assert reranker is not None
    assert reranker.llm_client.stats_store is store

    results = [MagicMock(spec=RetrievalResult) for _ in range(2)]
    for i, r in enumerate(results):
        r.chunk = MagicMock()
        r.chunk.text = f"text {i}"
        r.chunk.article_title = f"title {i}"
        r.chunk.section_name = "s"
        r.similarity_score = 0.5
    try:
        reranker.rerank("question", results, top_k=2)
    except Exception:
        pass  # parsing of the fake reply doesn't matter; the call was made

    assert fake_openai.chat.completions.create.called
    assert store.get_daily_cost() > 0
