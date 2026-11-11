"""Chat prompt assembly, history budgeting, query rewriting and titling.

Prior turns are context for resolving references only; only the numbered
Sources may be cited. Untrusted text (questions, history, chunk text) is never
passed through ``str.format``; templates are filled with ``str.replace`` on
fixed placeholders, and user-supplied text is inserted last.
"""

from pathlib import Path
from typing import Dict, List

import yaml
from loguru import logger

from src.chat.models import Message
from src.config_loader import get_model
from src.generation.llm_client import LLMClient
from src.storage.models import RetrievalResult

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_CHAT_PROMPTS_PATH = _CONFIG_DIR / "prompts_chat.yaml"
_BASE_PROMPTS_PATH = _CONFIG_DIR / "prompts.yaml"

HISTORY_MAX_CHARS = 6000
REWRITE_MAX_TURNS = 4
TITLE_MAX_CHARS = 60
_TITLE_WORDS = 6


def load_chat_prompts() -> Dict[str, str]:
    """Load chat prompts, adding shared prompts from prompts.yaml unchanged."""
    with open(_CHAT_PROMPTS_PATH, "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)
    with open(_BASE_PROMPTS_PATH, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f)
    for key in ("no_context_found", "medical_disclaimer"):
        prompts[key] = base[key]
    return prompts


def _turn_line(m: Message) -> str:
    label = "You" if m.role == "user" else "Assistant"
    return f"{label}: {m.content}"


def _turns(messages: List[Message]) -> List[Message]:
    return [m for m in messages if m.role != "settings"]


def format_history(messages: List[Message], max_chars: int = HISTORY_MAX_CHARS) -> str:
    """Render prior turns oldest-first, keeping the newest within the budget.

    Walks back from the newest turn and stops before exceeding ``max_chars``;
    the most recent turn is always kept, even if it alone exceeds the budget.
    """
    lines: List[str] = []
    used = 0
    for m in reversed(_turns(messages)):
        line = _turn_line(m)
        cost = len(line) + (1 if lines else 0)  # newline separator
        if lines and used + cost > max_chars:
            break
        lines.append(line)
        used += cost
    return "\n".join(reversed(lines))


def format_sources(results: List[RetrievalResult]) -> str:
    """Render numbered source blocks: ``[n] Title — Section`` then the text."""
    blocks = [
        f"[{i}] {r.chunk.article_title} — {r.chunk.section}\n{r.chunk.text}"
        for i, r in enumerate(results, start=1)
    ]
    return "\n\n".join(blocks)


def build_chat_messages(
    question: str,
    results: List[RetrievalResult],
    history: List[Message],
    prompts: Dict[str, str],
) -> List[dict]:
    """Return ``[system, user]`` with a sectioned user prompt.

    The question is passed verbatim; the rewritten query is only for retrieval.
    """
    parts: List[str] = []
    history_text = format_history(history)
    if history_text:
        parts.append("Earlier in this conversation:\n" + history_text)
    parts.append("Sources:\n" + format_sources(results))
    parts.append(prompts["sources_instruction"].strip())
    parts.append("Question:\n" + question)
    return [
        {"role": "system", "content": prompts["system_prompt"]},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def _fill(template: str, **values: str) -> str:
    """Fill ``{name}`` placeholders without interpreting braces in values."""
    # Single pass over the template so values are never re-scanned.
    out: List[str] = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            end = template.find("}", i)
            name = template[i + 1 : end] if end != -1 else None
            if name in values:
                out.append(values[name])
                i = end + 1
                continue
        out.append(template[i])
        i += 1
    return "".join(out)


def rewrite_query(
    llm: LLMClient, question: str, history: List[Message], prompts: Dict[str, str]
) -> str:
    """Rewrite a follow-up into a standalone retrieval query.

    Returns ``question`` unchanged when there is no history, the call fails,
    or the reply is blank.
    """
    turns = _turns(history)[-REWRITE_MAX_TURNS:]
    if not turns:
        return question
    prompt = _fill(
        prompts["rewrite_prompt"],
        history=format_history(turns),
        question=question,
    )
    try:
        result = llm.generate_messages(
            [{"role": "user", "content": prompt}],
            model=get_model("utility"),
            temperature=0,
            max_tokens=150,
        )
        rewritten = (result.get("answer") or "").strip()
    except Exception as e:
        logger.warning(f"Query rewrite failed, using original question: {e}")
        return question
    return rewritten or question


def fallback_title(question: str) -> str:
    """First 6 words of the question, capped at 60 characters."""
    return " ".join(question.split()[:_TITLE_WORDS])[:TITLE_MAX_CHARS].strip()


def clean_title(raw: str) -> str:
    """Strip surrounding quotes and trailing punctuation; cap at 60 characters."""
    title = raw.strip().strip("\"'`“”‘’").strip()
    title = title.rstrip(".,;:!?-– ").strip()
    return title[:TITLE_MAX_CHARS].strip()


def generate_title(llm: LLMClient, question: str, prompts: Dict[str, str]) -> str:
    """Generate a thread title with the utility model; fall back on any failure."""
    prompt = _fill(prompts["title_prompt"], question=question)
    try:
        result = llm.generate_messages(
            [{"role": "user", "content": prompt}],
            model=get_model("utility"),
            temperature=0,
            max_tokens=30,
        )
        title = clean_title(result.get("answer") or "")
    except Exception as e:
        logger.warning(f"Title generation failed, using fallback: {e}")
        return fallback_title(question)
    return title or fallback_title(question)
