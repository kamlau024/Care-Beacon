"""Tests for run aggregation and completeness checks (no network)."""

from types import SimpleNamespace as NS
from unittest.mock import patch

from evaluation.langfuse import judges, run_experiment as rx


def _item(*evals):
    return NS(evaluations=[NS(name=n, value=v) for n, v in evals])


def test_summarize_counts_scored_and_rates():
    result = NS(item_results=[
        _item(("grounded", 1), ("ask_latency_s", 1.0)),
        _item(("grounded", 0), ("ask_latency_s", 3.0)),
    ])
    s = rx.summarize(result)
    assert s["items"] == 2 and s["grounded_scored"] == 2
    assert s["grounded_pass_rate"] == 0.5 and s["median_ask_latency_s"] == 2.0
    assert rx.incomplete_reasons(s, 2) == []


def test_judge_failure_is_flagged():
    # second item lost its grounded score (evaluator exception swallowed by the SDK)
    result = NS(item_results=[_item(("grounded", 1)), _item(("ask_latency_s", 1.0))])
    reasons = rx.incomplete_reasons(rx.summarize(result), 2)
    assert len(reasons) == 1 and "1/2" in reasons[0] and "judge" in reasons[0]


def test_task_failure_is_flagged_and_zero_scores_handled():
    s = rx.summarize(NS(item_results=[]))
    assert s["grounded_scored"] == 0
    assert len(rx.incomplete_reasons(s, 78)) == 2


def test_main_exits_nonzero_on_incomplete_run(capsys):
    result = NS(run_name="r", item_results=[_item(("grounded", 1))])
    with patch.dict(rx.RUNNERS, {"search-baseline": lambda b, r: (result, 3)}):
        code = rx.main(["--dataset", "search-baseline", "--base-url", "u", "--run-name", "r"])
    assert code == 1
    assert "INCOMPLETE RUN" in capsys.readouterr().err


def test_empty_sources_skips_judge_and_scores_zero():
    with patch.object(judges, "_client", side_effect=AssertionError("no call")):
        score = judges.judge_grounded("q", "a", "  ")
    assert score.value == 0 and "no source text" in score.reason
