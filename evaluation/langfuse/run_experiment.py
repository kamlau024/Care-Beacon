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
import uuid
from pathlib import Path

import requests

from evaluation.langfuse import judges
from evaluation.langfuse.datasets import upsert_dataset

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "ragas" / "test_questions.json"
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
ASK_TIMEOUT_S = 120
CHAT_TIMEOUT_S = 120


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


# --- chat datasets (followups, safety) ---------------------------------------


class ChatFailure(Exception):
    """A chat turn failed (429, error frame, or no ``done``); the item must count as failed."""


def parse_sse(lines):
    """Yield ``(event, data)`` for each ``event:``/``data:`` frame in an iterable of lines."""
    event, data = None, []
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        line = line.rstrip("\r")
        if line == "":
            if event is not None or data:
                yield event, json.loads("\n".join(data)) if data else {}
            event, data = None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:"):].lstrip())
    if event is not None or data:
        yield event, json.loads("\n".join(data)) if data else {}


def run_turn(base_url: str, owner_key: str, message: str, thread_id: str | None) -> dict:
    """Send one chat turn and consume its SSE stream. Raises ChatFailure on any failure."""
    start = time.perf_counter()
    resp = requests.post(
        f"{base_url.rstrip('/')}/api/v1/chat",
        headers={"X-Owner-Key": owner_key},
        json={"thread_id": thread_id, "message": message, "include_full_text": True},
        stream=True,
        timeout=CHAT_TIMEOUT_S,
    )
    try:
        if resp.status_code == 429:
            raise ChatFailure("HTTP 429: daily cap reached")
        if resp.status_code >= 400:
            raise ChatFailure(f"HTTP {resp.status_code}")
        turn = {
            "thread_id": resp.headers.get("X-Thread-Id") or thread_id,
            "query": None,
            "citations": [],
            "first_token_s": None,
        }
        tokens: list[str] = []
        done = False
        for event, data in parse_sse(resp.iter_lines()):
            if event == "status" and data.get("stage") == "searching":
                turn["query"] = data.get("query")
            elif event == "citations":
                turn["citations"] = data.get("citations", [])
            elif event == "token":
                if turn["first_token_s"] is None:
                    turn["first_token_s"] = time.perf_counter() - start
                tokens.append(data.get("text", ""))
            elif event == "error":
                raise ChatFailure(f"error frame: {data.get('message')}")
            elif event == "done":
                done = True
                turn["thread_id"] = data.get("thread_id") or turn["thread_id"]
        if not done:
            raise ChatFailure("stream ended without a done frame")
        turn["total_s"] = time.perf_counter() - start
        turn["answer"] = "".join(tokens)
        turn["sources_text"] = "\n\n".join(
            c.get("full_text") or c.get("excerpt") or "" for c in turn["citations"]
        )
        return turn
    finally:
        resp.close()


def run_chat_item(base_url: str, turns: list[str]) -> dict:
    """Send all turns on one thread with a fresh owner key; return the last turn's record."""
    owner_key = str(uuid.uuid4())
    thread_id = None
    turn: dict = {}
    for message in turns:
        turn = run_turn(base_url, owner_key, message, thread_id)
        thread_id = turn["thread_id"]
    return turn


def make_chat_task(base_url: str):
    def task(*, item, **kwargs):
        return run_chat_item(base_url, item.input["turns"])

    return task


def _load_json(name: str, path: Path | None) -> list[dict]:
    return json.loads(Path(path or DATASETS_DIR / name).read_text())


def load_followup_items(path: Path | None = None) -> list[dict]:
    return [
        {
            "id": i["id"],
            "input": {"turns": i["turns"]},
            "expected_output": {"expected_reference": i["expected_reference"]},
        }
        for i in _load_json("followups.json", path)
    ]


def load_safety_items(path: Path | None = None) -> list[dict]:
    return [{"id": i["id"], "input": {"turns": i["turns"]}} for i in _load_json("safety.json", path)]


def load_safety_control_items(path: Path | None = None) -> list[dict]:
    """Each safety item's final turn alone, as a fresh single-turn thread.

    Compare this run's refusal_referral pass rate with the multi-turn
    ``safety`` run to see whether conversation drift weakens refusals.
    """
    return [
        {
            # Langfuse item ids are global, so namespace away from "safety-NNN".
            "id": f"control-{i['id']}",
            "input": {"turns": [i["turns"][-1]]},
            "metadata": {"source_item": i["id"], "source_turns": len(i["turns"])},
        }
        for i in _load_json("safety.json", path)
    ]


def followup_resolved_evaluator(*, input, output, expected_output, **kwargs):
    score = judges.judge_followup_resolved(
        input["turns"], output["answer"], expected_output["expected_reference"]
    )
    return {"name": "followup_resolved", "value": score.value, "comment": score.reason}


def chat_grounded_evaluator(*, input, output, **kwargs):
    score = judges.judge_grounded(input["turns"][-1], output["answer"], output["sources_text"])
    return {"name": "grounded", "value": score.value, "comment": score.reason}


def refusal_evaluator(*, input, output, **kwargs):
    score = judges.judge_refusal_referral(input["turns"][-1], output["answer"])
    return {"name": "refusal_referral", "value": score.value, "comment": score.reason}


def first_token_evaluator(*, output, **kwargs):
    if output["first_token_s"] is None:
        return []  # no token arrived: record no score rather than a fake 0.0
    return {"name": "first_token_s", "value": round(output["first_token_s"], 3)}


def turn_total_evaluator(*, output, **kwargs):
    return {"name": "turn_total_s", "value": round(output["total_s"], 3)}


def _run_chat_dataset(name, items, evaluators, base_url, run_name):
    from langfuse import Langfuse

    upsert_dataset(name, items)
    client = Langfuse()
    result = client.run_experiment(
        name=name,
        run_name=run_name,
        data=client.get_dataset(name).items,
        task=make_chat_task(base_url),
        evaluators=evaluators,
        max_concurrency=2,
    )
    return result, len(items)


def run_followups(base_url: str, run_name: str):
    return _run_chat_dataset(
        "followups",
        load_followup_items(),
        [followup_resolved_evaluator, chat_grounded_evaluator,
         first_token_evaluator, turn_total_evaluator],
        base_url,
        run_name,
    )


def run_safety(base_url: str, run_name: str):
    return _run_chat_dataset(
        "safety",
        load_safety_items(),
        [refusal_evaluator, first_token_evaluator, turn_total_evaluator],
        base_url,
        run_name,
    )


def run_safety_control(base_url: str, run_name: str):
    return _run_chat_dataset(
        "safety-control",
        load_safety_control_items(),
        [refusal_evaluator, first_token_evaluator, turn_total_evaluator],
        base_url,
        run_name,
    )


# Dataset name -> runner(base_url, run_name) -> (result, expected_item_count).
RUNNERS = {
    "search-baseline": run_search_baseline,
    "followups": run_followups,
    "safety": run_safety,
    "safety-control": run_safety_control,
}
# Scores every item must carry for a run to count as complete.
REQUIRED_SCORES = {
    "search-baseline": ("grounded",),
    "followups": ("followup_resolved", "grounded"),
    "safety": ("refusal_referral",),
    "safety-control": ("refusal_referral",),
}


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
        elif name in ("first_token_s", "turn_total_s"):
            summary[f"median_{name}"] = statistics.median(vals)
            summary[f"worst_{name}"] = max(vals)
        else:
            summary[f"{name}_scored"] = len(vals)
            summary[f"{name}_pass_rate"] = sum(vals) / len(vals)
    summary.setdefault("grounded_scored", 0)
    return summary


def incomplete_reasons(summary: dict, expected: int, required=("grounded",)) -> list[str]:
    """Reasons the run cannot be trusted as a full baseline (empty if complete)."""
    reasons = []
    if summary["items"] < expected:
        reasons.append(f"only {summary['items']}/{expected} items completed (task failures)")
    for name in required:
        scored = summary.get(f"{name}_scored", 0)
        if scored < expected:
            reasons.append(
                f"only {scored}/{expected} items got a {name} score (judge failures)"
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
    reasons = incomplete_reasons(summary, expected, REQUIRED_SCORES[args.dataset])
    for reason in reasons:
        print(f"WARNING: INCOMPLETE RUN - {reason}", file=sys.stderr)
    return 1 if reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
