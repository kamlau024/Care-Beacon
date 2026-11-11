"""Run a dataset experiment against the Care-Beacon API and post judge scores to Langfuse.

Usage (from the repo root):
    python -m evaluation.langfuse.run_experiment --dataset search-baseline \
        --base-url https://care-beacon-health.vercel.app --run-name search-baseline-YYYY-MM-DD
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import requests

from evaluation.langfuse import judges
from evaluation.langfuse.datasets import upsert_dataset

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "ragas" / "test_questions.json"
ASK_TIMEOUT_S = 120


# --- search-baseline -------------------------------------------------------


def load_search_baseline_items(path: Path = QUESTIONS_PATH) -> list[dict]:
    questions = json.loads(Path(path).read_text())
    return [
        {
            # Source ids repeat (46 unique in 78), so add the position to keep all items.
            "id": f"search-baseline-{i:03d}-{q['id']}",
            "input": {"question": q["question"]},
            "expected_output": {"ground_truth": q["ground_truth"]},
            "metadata": {
                k: q.get(k)
                for k in (
                    "question_type",
                    "difficulty",
                    "expected_source",
                    "source_article",
                    "source_section",
                )
            },
        }
        for i, q in enumerate(questions)
    ]


def make_ask_task(base_url: str):
    def task(*, item, **kwargs):
        question = item.input["question"]
        start = time.perf_counter()
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/v1/ask",
            json={"question": question, "include_full_text": True},
            timeout=ASK_TIMEOUT_S,
        )
        latency_s = time.perf_counter() - start
        resp.raise_for_status()
        data = resp.json()
        return {
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "latency_s": latency_s,
        }

    return task


def sources_text(sources: list[dict]) -> str:
    return "\n\n".join(s.get("full_text") or s.get("text_excerpt") or "" for s in sources)


def grounded_evaluator(*, input, output, **kwargs):
    score = judges.judge_grounded(
        input["question"], output["answer"], sources_text(output["sources"])
    )
    return {"name": "grounded", "value": score.value, "comment": score.reason}


def latency_evaluator(*, output, **kwargs):
    return {"name": "ask_latency_s", "value": round(output["latency_s"], 3)}


def run_search_baseline(base_url: str, run_name: str):
    from langfuse import Langfuse

    items = load_search_baseline_items()
    upsert_dataset("search-baseline", items)
    client = Langfuse()
    dataset = client.get_dataset("search-baseline")
    result = client.run_experiment(
        name="search-baseline",
        run_name=run_name,
        data=dataset.items,
        task=make_ask_task(base_url),
        evaluators=[grounded_evaluator, latency_evaluator],
        max_concurrency=4,
    )
    return result, len(items)


# Dataset name -> runner(base_url, run_name) -> (result, expected_item_count). Task 17 adds "followups" and "safety".
RUNNERS = {"search-baseline": run_search_baseline}


def summarize(result) -> dict:
    """Aggregate per-item evaluations into pass rates and median latency.

    The SDK swallows task and evaluator exceptions, so failed items simply have no
    evaluation. ``items`` counts surviving items and ``<name>_scored`` counts items
    that actually got each score; callers compare both with the dataset size.
    """
    values: dict[str, list[float]] = {}
    for item in result.item_results:
        for ev in item.evaluations:
            values.setdefault(ev.name, []).append(ev.value)
    summary = {"items": len(result.item_results)}
    for name, vals in values.items():
        if name == "ask_latency_s":
            summary["median_ask_latency_s"] = statistics.median(vals)
        else:
            summary[f"{name}_scored"] = len(vals)
            summary[f"{name}_pass_rate"] = sum(vals) / len(vals)
    summary.setdefault("grounded_scored", 0)
    return summary


def incomplete_reasons(summary: dict, expected: int) -> list[str]:
    """Reasons the run cannot be trusted as a full baseline (empty if complete)."""
    reasons = []
    if summary["items"] < expected:
        reasons.append(f"only {summary['items']}/{expected} items completed (task failures)")
    if summary["grounded_scored"] < expected:
        reasons.append(
            f"only {summary['grounded_scored']}/{expected} items got a grounded score (judge failures)"
        )
    return reasons


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, choices=sorted(RUNNERS))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args(argv)

    result, expected = RUNNERS[args.dataset](args.base_url, args.run_name)
    print(f"run: {result.run_name}")
    if getattr(result, "dataset_run_url", None):
        print(f"url: {result.dataset_run_url}")
    summary = summarize(result)
    for key, value in summary.items():
        print(f"{key}: {value:.3f}" if isinstance(value, float) else f"{key}: {value}")
    reasons = incomplete_reasons(summary, expected)
    for reason in reasons:
        print(f"WARNING: INCOMPLETE RUN - {reason}", file=sys.stderr)
    return 1 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
