"""Turn a Care Beacon answer into the MCP tool's output.

The generator's answer cites sources inline as ``[Source: Title - Section]``.
For agents these become ``[n]``, where n is the source's 1-based position in
the sources list: the same numbering the Search page uses
(web-client/lib/search-citations.ts), so an MCP answer and a Search answer to
the same question show the same numbers.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from src.api.models import CitationResponse
from src.mcp_server.schemas import AnswerCitation, CareBeaconAnswer

# A markdown link, e.g. "[Physical changes](https://www.cancer.ca/x#2181)".
_LINK = r"\[[^\[\]]*\]\([^()\s]*\)"
_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^()\s]*)\)")

# An inline citation: "[Source: Title - Section]", "[Source 2: Title - Section]"
# or "[Title - Section]". The section may itself be a markdown link (seen live),
# so the body allows one. `(?!\()` skips markdown links in the answer text.
_MARKER_RE = re.compile(
    r"\[(?:Source(?:\s+\d+)?:\s*)?(?P<body>(?:" + _LINK + r"|[^\[\]])+?)\](?!\()"
)


def split_section(section: str) -> Tuple[str, Optional[str]]:
    """Strip markdown link syntax from a section name.

    Returns the plain text and the first link's URL (None when there is no link).
    """
    urls = [m.group(2) for m in _LINK_RE.finditer(section)]
    plain = _LINK_RE.sub(lambda m: m.group(1), section).strip()
    return plain, (urls[0] if urls else None)


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def _title_matches(source_title: str, cited_title: str) -> bool:
    """Containment either way, as the Search page does."""
    st, ct = _norm(source_title), _norm(cited_title)
    return bool(ct) and (ct in st or st in ct)


def _section_matches(source_section: str, cited_section: str) -> bool:
    """Equal once markdown links are stripped from both sides."""
    return _norm(split_section(source_section)[0]) == _norm(split_section(cited_section)[0])


def _candidate_splits(body: str) -> List[Tuple[str, str]]:
    """Every way to split a marker body into (title, section) at a hyphen.

    Titles and sections can contain hyphens ("Non-Hodgkin lymphoma",
    "Long-term effects"), so the right split isn't knowable from the text alone.
    Splits are returned left to right; both halves are stripped and non-empty.
    """
    splits = []
    for i, ch in enumerate(body):
        if ch == "-":
            title, section = body[:i].strip(), body[i + 1 :].strip()
            if title and section:
                splits.append((title, section))
    return splits


def find_citation_index(sources: Sequence[CitationResponse], body: str) -> int:
    """Index of the source a marker body ("Title - Section") refers to, or -1.

    Use _candidate_splits(body) for the possible (title, section) readings, and
    _title_matches / _section_matches to compare a reading with a source
    (`source.article_title`, `source.section`).

    The tests in tests/test_mcp_format.py ("find_citation_index" block) pin the
    behaviour, including hyphens inside titles and sections.
    """
    # Rank every (reading, source) pair; lower is better, ties go to the earlier
    # source. An exact title beats containment, so "Non-Hodgkin lymphoma" never
    # resolves to "Hodgkin lymphoma" when the exact source is also present.
    #   0 exact title + section   1 contained title + section
    #   2 exact title only        3 contained title only
    best: Optional[Tuple[int, int]] = None
    for title, section in _candidate_splits(body):
        for i, s in enumerate(sources):
            if not _title_matches(s.article_title, title):
                continue
            exact = _norm(s.article_title) == _norm(title)
            rank = (0 if _section_matches(s.section, section) else 2) + (0 if exact else 1)
            if best is None or (rank, i) < best:
                best = (rank, i)
    return -1 if best is None else best[1]


def renumber(answer: str, sources: Sequence[CitationResponse]) -> Tuple[str, int]:
    """Replace inline source markers with [n].

    Returns the new text and how many markers matched no source (those stay as
    their original text, and the count goes in the trace as `unmatched_markers`).
    Bracketed text with no hyphen (e.g. "[sic]") is not a marker and isn't counted.
    """
    unmatched = 0

    def replace(m: re.Match) -> str:
        nonlocal unmatched
        body = m.group("body")
        if "-" not in body:
            return m.group(0)
        i = find_citation_index(sources, body)
        if i == -1:
            unmatched += 1
            return m.group(0)
        return f"[{i + 1}]"

    return _MARKER_RE.sub(replace, answer), unmatched


def build_citations(
    sources: Sequence[CitationResponse], *, include_text: bool
) -> List[AnswerCitation]:
    """One AnswerCitation per source, numbered by position (never-cited ones included)."""
    citations = []
    for i, s in enumerate(sources, 1):
        section, section_url = split_section(s.section)
        citations.append(
            AnswerCitation(
                n=i,
                title=s.article_title,
                section=section,
                section_url=section_url,
                url=s.url,
                source=s.source,
                similarity=round(s.similarity_score, 4),
                excerpt=s.text_excerpt,
                text=s.full_text if include_text else None,
            )
        )
    return citations


def render_markdown(result: CareBeaconAnswer) -> str:
    """The readable text block: answer, numbered Sources list, then disclaimer."""
    parts = [result.answer.strip()]
    if result.citations:
        lines = [
            f"[{c.n}] {c.title} — {c.section} ({c.source}). {c.url}" for c in result.citations
        ]
        parts.append("**Sources**\n" + "\n".join(lines))
    if result.disclaimer:
        parts.append(result.disclaimer.strip())
    return "\n\n".join(parts) + "\n"
