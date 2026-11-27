"""Pydantic models for the MCP tool's structured output (plan §3.2, §3.3).

`CareBeaconAnswer` is the tool's return annotation, so the SDK publishes its
JSON Schema as the tool's `outputSchema` and validates `structuredContent`
against it.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AnswerCitation(BaseModel):
    """One source passage, numbered as the answer's [n] markers refer to it."""

    n: int = Field(ge=1, description="The number used in the answer's [n] markers.")
    title: str
    section: str = Field(description="Plain section name (markdown link syntax stripped).")
    section_url: Optional[str] = Field(
        default=None, description="Deep link to the section if the source page has one."
    )
    url: str
    source: str
    similarity: float
    excerpt: str
    text: Optional[str] = Field(
        default=None, description="Full passage, only when include_source_text was true."
    )


class AppliedSettings(BaseModel):
    """The settings actually applied, after defaults."""

    sources: List[str]
    min_similarity: float
    max_results: int


class AnswerMeta(BaseModel):
    model: str
    cached: bool
    cost_usd: float
    duration_ms: int
    trace_id: Optional[str] = None


class CareBeaconAnswer(BaseModel):
    """A grounded answer with numbered citations."""

    answer: str = Field(description="Markdown answer with inline [n] citation markers.")
    answered: bool = Field(
        description="False when no source met min_similarity and Care Beacon declined to answer."
    )
    citations: List[AnswerCitation]
    disclaimer: str
    settings: AppliedSettings
    meta: AnswerMeta


class ErrorInfo(BaseModel):
    """Stable, machine-readable error carried in an isError result."""

    code: str
    message: str
    field: Optional[str] = None
    retry_after_s: Optional[int] = None
    resets_at: Optional[str] = None
