"""Tests for chat prompt assembly, history budgeting and query rewriting."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.chat.models import Message
from src.chat.prompt import (
    build_chat_messages,
    clean_title,
    fallback_title,
    format_history,
    format_sources,
    generate_title,
    load_chat_prompts,
    rewrite_query,
)
from src.storage.models import Chunk, RetrievalResult

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def msg(role, content, i=0):
    return Message(
        id=f"m{i}",
        thread_id="t1",
        role=role,
        content=content,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def result(text="Chunk text", title="Title", section="Sec"):
    chunk = Chunk(
        chunk_id="c1",
        text=text,
        article_id="a1",
        article_title=title,
        url="http://x",
        breadcrumbs=[],
        section=section,
    )
    return RetrievalResult(chunk=chunk, similarity_score=0.9)


class FakeLLM:
    def __init__(self, answer="", raises=False):
        self.answer = answer
        self.raises = raises
        self.calls = []

    def generate_messages(self, messages, max_tokens=None, temperature=None, model=None):
        self.calls.append({"messages": messages, "model": model})
        if self.raises:
            raise RuntimeError("boom")
        return {"answer": self.answer}


@pytest.fixture
def prompts():
    return load_chat_prompts()


def test_system_prompt_keeps_guidelines_5_to_8_verbatim(prompts):
    with open(CONFIG_DIR / "prompts_eval.yaml") as f:
        eval_prompt = yaml.safe_load(f)["system_prompt"]
    lines = [l.strip() for l in eval_prompt.splitlines()]
    expected = [
        "5. Use simple, patient-friendly language",
        "6. Be empathetic and supportive in your tone",
        "7. Never provide personal medical advice or diagnoses",
        "8. Always remind patients to consult with healthcare providers",
    ]
    for line in expected:
        assert line in lines  # present in the source prompt
        assert line in prompts["system_prompt"]


def test_load_adds_shared_prompts_unchanged(prompts):
    with open(CONFIG_DIR / "prompts.yaml") as f:
        base = yaml.safe_load(f)
    assert prompts["no_context_found"] == base["no_context_found"]
    assert prompts["medical_disclaimer"] == base["medical_disclaimer"]
    for key in ("system_prompt", "sources_instruction", "rewrite_prompt", "title_prompt"):
        assert prompts[key].strip()


def test_format_sources_numbered_from_one():
    out = format_sources([result("A text", "T1", "S1"), result("B text", "T2", "S2")])
    assert out == "[1] T1 — S1\nA text\n\n[2] T2 — S2\nB text"


def test_no_history_section_on_first_turn(prompts):
    out = build_chat_messages("Q?", [result()], [], prompts)
    assert [m["role"] for m in out] == ["system", "user"]
    assert "Earlier in this conversation:" not in out[1]["content"]
    assert out[1]["content"].index("Sources:") < out[1]["content"].index("Question:")


def test_history_section_precedes_sources(prompts):
    out = build_chat_messages("Q?", [result()], [msg("user", "hi"), msg("assistant", "yo")], prompts)
    c = out[1]["content"]
    assert c.index("Earlier in this conversation:") < c.index("Sources:") < c.index("Question:")
    assert "You: hi" in c and "Assistant: yo" in c


def test_history_budget_keeps_newest_and_drops_oldest():
    hist = [msg("user", "old" * 50, 1), msg("assistant", "mid" * 50, 2), msg("user", "new" * 50, 3)]
    out = format_history(hist, max_chars=400)
    assert "new" in out and "old" not in out
    assert out.index("mid") < out.index("new")  # chronological order


def test_history_always_keeps_last_turn_even_if_over_budget():
    hist = [msg("user", "a", 1), msg("assistant", "z" * 500, 2)]
    out = format_history(hist, max_chars=50)
    assert "z" * 500 in out and "You: a" not in out


def test_settings_rows_excluded_from_history():
    hist = [msg("user", "hello"), msg("settings", "SECRET-SETTINGS"), msg("assistant", "hi")]
    out = format_history(hist)
    assert "SECRET-SETTINGS" not in out
    assert out == "You: hello\nAssistant: hi"


def test_question_passed_verbatim_not_rewritten(prompts):
    q = "What about {braces} and {0} here?"
    out = build_chat_messages(q, [result("text {x} {}")], [msg("user", "{a}")], prompts)
    c = out[1]["content"]
    assert c.endswith("Question:\n" + q)
    assert "text {x} {}" in c and "You: {a}" in c


def test_rewrite_returns_question_when_llm_raises(prompts):
    llm = FakeLLM(raises=True)
    assert rewrite_query(llm, "and side effects?", [msg("user", "chemo")], prompts) == "and side effects?"


def test_rewrite_skipped_on_first_turn(prompts):
    llm = FakeLLM(answer="x")
    assert rewrite_query(llm, "Q", [], prompts) == "Q"
    assert rewrite_query(llm, "Q", [msg("settings", "s")], prompts) == "Q"
    assert llm.calls == []


def test_rewrite_blank_reply_returns_question(prompts):
    assert rewrite_query(FakeLLM(answer="  \n"), "Q", [msg("user", "a")], prompts) == "Q"


def test_rewrite_uses_utility_model_and_last_four_turns(prompts):
    from src.config_loader import get_model

    hist = [msg("user" if i % 2 == 0 else "assistant", f"turn{i}", i) for i in range(8)]
    llm = FakeLLM(answer=" standalone question \n")
    assert rewrite_query(llm, "Q {x}", hist, prompts) == "standalone question"
    call = llm.calls[0]
    assert call["model"] == get_model("utility")
    text = "".join(m["content"] for m in call["messages"])
    assert "turn7" in text and "turn4" in text and "turn3" not in text
    assert "Q {x}" in text


def test_title_falls_back_on_error(prompts):
    q = "What are the common side effects of chemotherapy for breast cancer patients"
    assert generate_title(FakeLLM(raises=True), q, prompts) == fallback_title(q)
    assert generate_title(FakeLLM(answer=" "), q, prompts) == fallback_title(q)


def test_generate_title_cleans_reply(prompts):
    llm = FakeLLM(answer='"Chemo side effects."')
    assert generate_title(llm, "q", prompts) == "Chemo side effects"


def test_fallback_and_clean_title_caps():
    assert fallback_title("one two three four five six seven eight") == "one two three four five six"
    assert len(fallback_title("x" * 200)) == 60
    assert clean_title("'Hello world!'  ") == "Hello world"
    assert len(clean_title("y" * 100)) == 60
