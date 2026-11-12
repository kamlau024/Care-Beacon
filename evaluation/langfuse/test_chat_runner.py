"""Chat runner tests: SSE parsing, per-item recording, failure modes. HTTP is mocked."""

import json
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

from evaluation.langfuse import judges, run_experiment as rx
from evaluation.langfuse.judges import Score

DATASETS = rx.DATASETS_DIR

RECORDED_STREAM = (
    'event: status\ndata: {"stage": "rewriting"}\n\n'
    'event: status\ndata: {"stage": "searching", "query": "radiation therapy fatigue duration"}\n\n'
    'event: status\ndata: {"stage": "ranking"}\n\n'
    'event: citations\ndata: {"citations": [{"n": 1, "article_title": "A", "section": "S", '
    '"url": "u1", "source": "bc", "similarity_score": 0.9, "excerpt": "e1", "full_text": "Full one."},'
    ' {"n": 2, "article_title": "B", "section": "S", "url": "u2", "source": "ccs", '
    '"similarity_score": 0.8, "excerpt": "e2", "full_text": "Full two."}]}\n\n'
    'event: token\ndata: {"text": "Fatigue "}\n\n'
    'event: token\ndata: {"text": "can last weeks [1]."}\n\n'
    'event: done\ndata: {"thread_id": "t-1", "message_id": "m-1", "disclaimer": "d"}\n\n'
)


class FakeResp:
    def __init__(self, text="", status=200, headers=None, json_body=None):
        self.status_code = status
        self.headers = headers or {}
        self._text = text
        self._json = json_body

    def iter_lines(self, decode_unicode=False):
        return iter(self._text.split("\n"))

    def json(self):
        return self._json

    def close(self):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _post_returning(*responses):
    it = iter(responses)
    calls = []

    def post(url, **kw):
        calls.append((url, kw))
        return next(it)

    return post, calls


def test_parse_sse_yields_frames_and_ignores_comments():
    text = ': keepalive\nevent: token\ndata: {"text": "hi"}\n\nevent: done\ndata: {}\n'
    frames = list(rx.parse_sse(text.split("\n")))
    assert frames == [("token", {"text": "hi"}), ("done", {})]


def test_runner_parses_frames_from_a_recorded_stream():
    resp = FakeResp(RECORDED_STREAM, headers={"X-Thread-Id": "t-1"})
    post, calls = _post_returning(resp)
    with patch.object(rx.requests, "post", post):
        turn = rx.run_turn("https://x.test/", "owner", "How long does it last?", None)
    assert turn["thread_id"] == "t-1"
    assert turn["query"] == "radiation therapy fatigue duration"
    assert turn["answer"] == "Fatigue can last weeks [1]."
    assert turn["sources_text"] == "Full one.\n\nFull two."
    assert turn["first_token_s"] is not None and turn["first_token_s"] <= turn["total_s"]
    url, kw = calls[0]
    assert url == "https://x.test/api/v1/chat"
    assert kw["headers"]["X-Owner-Key"] == "owner"
    assert kw["json"] == {
        "thread_id": None,
        "message": "How long does it last?",
        "include_full_text": True,
    }


def test_chat_item_sends_turns_in_order_on_one_thread():
    post, calls = _post_returning(
        FakeResp(RECORDED_STREAM, headers={"X-Thread-Id": "t-1"}),
        FakeResp(RECORDED_STREAM, headers={"X-Thread-Id": "t-1"}),
    )
    with patch.object(rx.requests, "post", post):
        out = rx.run_chat_item("https://x.test", ["first question", "second question"])
    assert [c[1]["json"]["thread_id"] for c in calls] == [None, "t-1"]
    assert [c[1]["json"]["message"] for c in calls] == ["first question", "second question"]
    owner_keys = {c[1]["headers"]["X-Owner-Key"] for c in calls}
    assert len(owner_keys) == 1
    assert out["answer"].startswith("Fatigue") and out["query"]


def test_error_frame_fails_the_item():
    stream = 'event: error\ndata: {"message": "boom"}\n\n'
    post, _ = _post_returning(FakeResp(stream, headers={"X-Thread-Id": "t"}))
    with patch.object(rx.requests, "post", post), pytest.raises(rx.ChatFailure, match="boom"):
        rx.run_chat_item("https://x.test", ["a question"])


def test_429_fails_the_item():
    post, _ = _post_returning(FakeResp(status=429, json_body={"detail": "cap"}))
    with patch.object(rx.requests, "post", post), pytest.raises(rx.ChatFailure, match="429"):
        rx.run_chat_item("https://x.test", ["a question"])


def test_stream_without_done_fails_the_item():
    truncated = RECORDED_STREAM.split("event: done")[0]
    post, _ = _post_returning(FakeResp(truncated, headers={"X-Thread-Id": "t"}))
    with patch.object(rx.requests, "post", post), pytest.raises(rx.ChatFailure, match="done"):
        rx.run_chat_item("https://x.test", ["a question"])


def test_failure_in_earlier_turn_aborts_the_thread():
    post, calls = _post_returning(
        FakeResp(status=429, json_body={}), FakeResp(RECORDED_STREAM)
    )
    with patch.object(rx.requests, "post", post), pytest.raises(rx.ChatFailure):
        rx.run_chat_item("https://x.test", ["one question", "two question"])
    assert len(calls) == 1


def test_evaluators_score_last_turn():
    output = {"answer": "a", "sources_text": "src", "query": "q",
              "first_token_s": 1.5, "total_s": 4.0}
    with patch.object(judges, "judge_followup_resolved", return_value=Score(1, "ok")) as f, \
         patch.object(judges, "judge_grounded", return_value=Score(0, "no")) as g:
        r = rx.followup_resolved_evaluator(
            input={"turns": ["a", "b"]}, output=output,
            expected_output={"expected_reference": "ref"})
        gr = rx.chat_grounded_evaluator(input={"turns": ["a", "b"]}, output=output)
    f.assert_called_once_with(["a", "b"], "a", "ref")
    g.assert_called_once_with("b", "a", "src")
    assert (r["name"], r["value"]) == ("followup_resolved", 1)
    assert (gr["name"], gr["value"]) == ("grounded", 0)
    with patch.object(judges, "judge_refusal_referral", return_value=Score(1, "ok")) as s:
        sr = rx.refusal_evaluator(input={"turns": ["a", "b"]}, output=output)
    s.assert_called_once_with("b", "a")
    assert (sr["name"], sr["value"]) == ("refusal_referral", 1)
    assert rx.first_token_evaluator(output=output)["value"] == 1.5
    assert rx.turn_total_evaluator(output=output)["value"] == 4.0


def test_summarize_reports_latency_median_and_worst():
    result = NS(item_results=[
        NS(evaluations=[NS(name="first_token_s", value=1.0), NS(name="turn_total_s", value=5.0)]),
        NS(evaluations=[NS(name="first_token_s", value=3.0), NS(name="turn_total_s", value=9.0)]),
    ])
    s = rx.summarize(result)
    assert s["median_first_token_s"] == 2.0 and s["worst_first_token_s"] == 3.0
    assert s["worst_turn_total_s"] == 9.0


def test_incomplete_reasons_uses_the_datasets_required_score():
    s = rx.summarize(NS(item_results=[
        NS(evaluations=[NS(name="refusal_referral", value=1)])]))
    assert rx.incomplete_reasons(s, 1, ("refusal_referral",)) == []
    assert rx.incomplete_reasons(s, 2, ("refusal_referral",))


def test_dataset_files_meet_the_brief():
    fu = json.loads((DATASETS / "followups.json").read_text())
    sf = json.loads((DATASETS / "safety.json").read_text())
    assert len(fu) >= 20 and len(sf) >= 8
    for items in (fu, sf):
        assert len({i["id"] for i in items}) == len(items)
        for i in items:
            assert 2 <= len(i["turns"]) <= 3
            assert all(3 <= len(t) <= 500 for t in i["turns"])
    assert all(i["expected_reference"].strip() for i in fu)


def test_load_items_shapes_langfuse_items():
    fu = rx.load_followup_items()
    assert fu[0]["input"]["turns"] and fu[0]["expected_output"]["expected_reference"]
    assert rx.load_safety_items()[0]["input"]["turns"]
    assert {"followups", "safety"} <= set(rx.RUNNERS)


def test_utf8_bytes_are_decoded_intact():
    stream = ('event: token\ndata: {"text": "café — 5 µg"}\n\n'
              'event: done\ndata: {"thread_id": "t"}\n\n').encode("utf-8")

    class ByteResp(FakeResp):
        def iter_lines(self, decode_unicode=False):
            assert not decode_unicode  # requests would guess ISO-8859-1
            return iter(stream.split(b"\n"))

    post, _ = _post_returning(ByteResp(headers={"X-Thread-Id": "t"}))
    with patch.object(rx.requests, "post", post):
        turn = rx.run_turn("https://x.test", "owner", "a question", None)
    assert turn["answer"] == "café — 5 µg"


def test_no_token_records_no_first_token_score_and_stats_skip_it():
    assert rx.first_token_evaluator(output={"first_token_s": None, "total_s": 2.0}) == []
    result = NS(item_results=[
        NS(evaluations=[NS(name="first_token_s", value=2.0)]),
        NS(evaluations=[]),  # item with no token: no first_token_s score
        NS(evaluations=[NS(name="first_token_s", value=4.0)]),
    ])
    s = rx.summarize(result)
    assert s["median_first_token_s"] == 3.0 and s["worst_first_token_s"] == 4.0


def test_safety_set_has_three_turn_drift_threads():
    sf = json.loads((DATASETS / "safety.json").read_text())
    assert sum(len(i["turns"]) == 3 for i in sf) >= 4 + 1
