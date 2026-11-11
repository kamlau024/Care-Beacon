"""Unit tests for the LLM-as-judge scorers. OpenAI is mocked; no network calls."""

import json
from unittest.mock import MagicMock, patch

import pytest

from evaluation.langfuse import judges
from evaluation.langfuse.judges import Score


def _fake_client(content):
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return client


@pytest.fixture
def call_judge():
    def _call(content):
        client = _fake_client(content)
        with patch.object(judges, "_client", return_value=client):
            score = judges.judge_grounded("q", "a", "sources")
        return score, client

    return _call


def test_valid_reply_returns_that_score(call_judge):
    score, _ = call_judge(json.dumps({"score": 1, "reason": "supported"}))
    assert score == Score(1, "supported")
    score, _ = call_judge(json.dumps({"score": 0, "reason": "not supported"}))
    assert score == Score(0, "not supported")


def test_out_of_range_score_becomes_zero(call_judge):
    score, _ = call_judge(json.dumps({"score": 2, "reason": "x"}))
    assert score.value == 0
    assert "unparseable" in score.reason


def test_non_json_becomes_zero(call_judge):
    score, _ = call_judge("not json at all")
    assert score.value == 0
    assert score.reason.startswith("unparseable judge reply")


def test_non_object_json_becomes_zero(call_judge):
    score, _ = call_judge("[1, 2]")
    assert score == Score(0, "unparseable judge reply: [1, 2]")


def test_boolean_score_is_rejected(call_judge):
    score, _ = call_judge(json.dumps({"score": True, "reason": "x"}))
    assert score.value == 0


def test_call_uses_model_temperature_and_json_format(call_judge):
    _, client = call_judge(json.dumps({"score": 1, "reason": "ok"}))
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0
    assert kwargs["response_format"] == {"type": "json_object"}


def test_other_judges_put_inputs_in_prompt():
    client = _fake_client(json.dumps({"score": 1, "reason": "ok"}))
    with patch.object(judges, "_client", return_value=client):
        r = judges.judge_refusal_referral("I have chest pain", "Call 911")
        f = judges.judge_followup_resolved(
            ["What is X?", "And its cause?"], "Because Y", "X is caused by Y"
        )
    assert r == Score(1, "ok") and f == Score(1, "ok")
    prompts = [
        c.kwargs["messages"][-1]["content"]
        for c in client.chat.completions.create.call_args_list
    ]
    assert "I have chest pain" in prompts[0] and "Call 911" in prompts[0]
    assert "And its cause?" in prompts[1] and "X is caused by Y" in prompts[1]


def test_search_baseline_items_are_all_present_with_unique_ids():
    from evaluation.langfuse.run_experiment import load_search_baseline_items

    items = load_search_baseline_items()
    assert len(items) == 78
    assert len({i["id"] for i in items}) == 78
