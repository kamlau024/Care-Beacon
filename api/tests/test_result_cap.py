"""cap_results: the MCP tool's max_results is a real cap, Search's is not.

With re-ranking on, retrieval returns every passage above min_similarity and
max_results only sizes the candidate pool. Search keeps that behaviour; the MCP
path asks for cap_results=True so the answer is written from, and cites, at most
max_results passages.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.api.ask_service import answer_question
from src.api.models import QuestionRequest
from src.caching.redis_cache import CacheConfig, RedisCache
from src.generation.answer_generator import AnswerGenerator, GenerationConfig
from src.retrieval.models import Query, RetrievalResult, RetrievedContext
from src.storage.models import Chunk


def _result(i, score):
    chunk = Chunk(
        chunk_id=f"c{i}",
        text=f"Passage {i} text.",
        article_id=f"a{i}",
        article_title=f"Article {i}",
        url=f"https://example.org/{i}",
        breadcrumbs=[],
        cancer_type="General",
        section=f"Section {i}",
        paragraph_index=0,
        total_paragraphs=1,
        embedding=[0.0],
    )
    return RetrievalResult(chunk=chunk, similarity_score=score, rank=i)


@pytest.fixture
def generator():
    engine = Mock()
    engine.retrieve_text.return_value = RetrievedContext(
        query=Query(text="q", max_results=2),
        results=[_result(i, 0.9 - i * 0.1) for i in range(4)],
        total_chunks=4,
        retrieval_time_ms=1.0,
    )
    llm = Mock()
    llm.generate.return_value = {
        "answer": "An answer.",
        "tokens_used": {"input": 1, "output": 1, "total": 2},
        "cost": 0.0,
        "model": "gpt-4o-mini",
        "generation_time_ms": 1.0,
    }
    cache = Mock()
    cache.get.return_value = None
    g = AnswerGenerator(
        retrieval_engine=engine,
        llm_client=llm,
        config=GenerationConfig(model="gpt-4o-mini", max_context_chunks=30),
        cache=cache,
    )
    return g


def _prompt(g):
    return g.llm_client.generate.call_args.kwargs["user_prompt"]


def test_capped_answer_uses_and_cites_only_the_top_passages(generator):
    answer = generator.generate_answer("q", max_results=2, cap_results=True)
    assert [c.article_title for c in answer.citations] == ["Article 0", "Article 1"]
    assert len(answer.context_used.results) == 2
    prompt = _prompt(generator)
    assert "Passage 1 text." in prompt and "Passage 2 text." not in prompt


def test_uncapped_answer_keeps_every_passage_as_search_does(generator):
    answer = generator.generate_answer("q", max_results=2)
    assert len(answer.citations) == 4
    assert "Passage 3 text." in _prompt(generator)


def test_cap_is_part_of_the_cache_lookup_and_store(generator):
    generator.generate_answer("q", max_results=2, cap_results=True)
    assert generator.cache.get.call_args.kwargs["cap_results"] is True
    assert generator.cache.set.call_args.kwargs["cap_results"] is True


@pytest.fixture
def cache():
    with patch("redis.Redis", return_value=MagicMock()):
        return RedisCache(config=CacheConfig())


def test_capped_and_uncapped_answers_never_share_a_cache_entry(cache):
    plain = cache._generate_cache_key("q", None, 5, 0.5)
    capped = cache._generate_cache_key("q", None, 5, 0.5, cap_results=True)
    assert capped != plain


def test_search_cache_keys_are_unchanged(cache):
    # Existing Search entries must stay valid: the uncapped key is the old key.
    assert cache._generate_cache_key("q", None, 5, 0.5) == cache._generate_cache_key(
        "q", None, 5, 0.5, cap_results=False
    )
    assert cache._generate_cache_key("q", None, 5, 0.5) == (
        "care_beacon:answer:"
        + __import__("hashlib").sha256(
            b'{"filters": {}, "max_results": 5, "min_similarity": 0.5, "question": "q"}'
        ).hexdigest()
    )


def test_answer_question_passes_the_cap_and_defaults_it_off():
    g = MagicMock()
    g.generate_answer.return_value = MagicMock(citations=[], cached=False)
    req = QuestionRequest(question="Side effects?")
    with patch("src.api.ask_service._response"):
        answer_question(req, g)
        assert g.generate_answer.call_args.kwargs["cap_results"] is False
        answer_question(req, g, cap_results=True)
        assert g.generate_answer.call_args.kwargs["cap_results"] is True
