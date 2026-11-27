"""Tests for the MCP answer formatting (citation numbering, section links, Markdown).

The numbering matches the Search page (web-client/lib/search-citations.ts): a
marker's number is its source's 1-based position in the sources list, so the
cases from search-citations.test.ts are ported here first.
"""

import pytest

from src.api.models import CitationResponse
from src.mcp_server.format import (
    build_citations,
    find_citation_index,
    render_markdown,
    renumber,
    split_section,
)
from src.mcp_server.schemas import AnswerMeta, AppliedSettings, CareBeaconAnswer


def src(title, section, source="BC Cancer", full_text=None):
    return CitationResponse(
        article_title=title,
        section=section,
        url=f"https://example.org/{title.replace(' ', '-')}",
        paragraph_index=0,
        text_excerpt=f"{title} excerpt",
        similarity_score=0.8,
        source=source,
        full_text=full_text,
    )


SOURCES = [
    src("Managing side effects", "Fatigue"),
    src("Managing side effects", "Nausea"),
    src("Chemotherapy", "Overview", "Canadian Cancer Society"),
]


# --- split_section -----------------------------------------------------------


def test_split_section_plain_text_is_unchanged():
    assert split_section("Fatigue") == ("Fatigue", None)


def test_split_section_strips_a_markdown_link():
    # Seen live on /ask: section stored as a raw markdown link.
    assert split_section("[Physical changes](https://www.cancer.ca/x#2181)") == (
        "Physical changes",
        "https://www.cancer.ca/x#2181",
    )


def test_split_section_strips_a_link_inside_text():
    assert split_section("After treatment: [Diet](https://e.org/d)") == (
        "After treatment: Diet",
        "https://e.org/d",
    )


# --- find_citation_index (ported from findSourceIndex) -----------------------


def test_prefers_the_source_whose_title_and_section_both_match():
    assert find_citation_index(SOURCES, "Managing side effects - Nausea") == 1


def test_falls_back_to_the_first_title_match_when_no_section_matches():
    assert find_citation_index(SOURCES, "managing side effects - Hair loss") == 0


def test_returns_minus_one_when_no_title_matches():
    assert find_citation_index(SOURCES, "Radiation - Overview") == -1


def test_a_hyphen_inside_the_title_does_not_split_it():
    sources = [
        src("Hodgkin lymphoma", "Symptoms"),
        src("Non-Hodgkin lymphoma", "Symptoms"),
    ]
    assert find_citation_index(sources, "Non-Hodgkin lymphoma - Symptoms") == 1


def test_a_hyphen_inside_the_section_does_not_split_it():
    sources = [src("Chemotherapy", "Side effects"), src("Chemotherapy", "Long-term effects")]
    assert find_citation_index(sources, "Chemotherapy - Long-term effects") == 1


def test_matches_a_section_stored_as_a_markdown_link():
    sources = [
        src("Coping", "Emotions"),
        src("Coping", "[Physical changes](https://e.org/c#2181)"),
    ]
    assert find_citation_index(sources, "Coping - Physical changes") == 1
    assert find_citation_index(sources, "Coping - [Physical changes](https://e.org/c#2181)") == 1


# --- renumber (ported from segmentAnswer) ------------------------------------


def test_numbers_markers_by_source_position():
    text = (
        "Tiredness is common [Source: Managing side effects - Fatigue]. "
        "Ask about medicine [Chemotherapy - Overview]."
    )
    assert renumber(text, SOURCES) == ("Tiredness is common [1]. Ask about medicine [3].", 0)


def test_keeps_an_unmatched_marker_as_text_and_counts_it():
    assert renumber("A [Source: Unknown - X] b", SOURCES) == ("A [Source: Unknown - X] b", 1)


def test_text_without_markers_is_unchanged():
    assert renumber("No citations here.", SOURCES) == ("No citations here.", 0)


def test_numbered_source_markers_are_renumbered():
    # The prompt shows sources as "[Source 2: Title - Section]"; the model sometimes copies that.
    assert renumber("Nausea [Source 2: Managing side effects - Nausea].", SOURCES) == (
        "Nausea [2].",
        0,
    )


def test_markdown_links_in_the_answer_are_left_alone():
    text = "See [BC Cancer - home](https://bccancer.bc.ca) for more."
    assert renumber(text, SOURCES) == (text, 0)


def test_marker_with_a_link_in_its_section_is_renumbered():
    sources = [src("Coping", "[Physical changes](https://e.org/c#2181)")]
    text = "Changes happen [Source: Coping - [Physical changes](https://e.org/c#2181)]."
    assert renumber(text, sources) == ("Changes happen [1].", 0)


# --- build_citations ---------------------------------------------------------


def test_citations_keep_source_order_and_strip_section_links():
    sources = [src("Coping", "[Physical changes](https://e.org/c#2181)", full_text="Full.")]
    [c] = build_citations(sources, include_text=False)
    assert c.n == 1
    assert c.title == "Coping"
    assert c.section == "Physical changes"
    assert c.section_url == "https://e.org/c#2181"
    assert c.excerpt == "Coping excerpt"
    assert c.text is None


def test_citations_include_full_text_only_when_asked():
    sources = [src("Coping", "Emotions", full_text="Full passage.")]
    [c] = build_citations(sources, include_text=True)
    assert c.text == "Full passage."


# --- render_markdown ---------------------------------------------------------


def test_markdown_has_answer_sources_and_disclaimer():
    citations = build_citations(SOURCES[:1], include_text=False)
    result = CareBeaconAnswer(
        answer="Tiredness is common [1].",
        answered=True,
        citations=citations,
        disclaimer="Educational only.",
        settings=AppliedSettings(sources=["BC Cancer"], min_similarity=0.5, max_results=5),
        meta=AnswerMeta(model="gpt-4o-mini", cached=False, cost_usd=0.0, duration_ms=1),
    )
    md = render_markdown(result)
    assert md.startswith("Tiredness is common [1].")
    assert "**Sources**" in md
    assert (
        "[1] Managing side effects — Fatigue (BC Cancer). https://example.org/Managing-side-effects"
        in md
    )
    assert md.rstrip().endswith("Educational only.")


def test_markdown_for_an_unanswered_question_has_no_sources_list():
    result = CareBeaconAnswer(
        answer="I couldn't find relevant information.",
        answered=False,
        citations=[],
        disclaimer="Educational only.",
        settings=AppliedSettings(sources=["BC Cancer"], min_similarity=0.9, max_results=5),
        meta=AnswerMeta(model="gpt-4o-mini", cached=False, cost_usd=0.0, duration_ms=1),
    )
    assert "**Sources**" not in render_markdown(result)
