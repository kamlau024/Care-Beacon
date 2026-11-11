"""Pydantic models for chat threads and messages."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from src.api.filters import configured_sources


class ThreadSettings(BaseModel):
    sources: list[str]
    min_similarity: float

    @field_validator("sources")
    @classmethod
    def _valid_sources(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("sources must not be empty")
        unknown = [s for s in v if s not in configured_sources()]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}")
        return v

    @field_validator("min_similarity")
    @classmethod
    def _valid_similarity(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("min_similarity must be between 0 and 1")
        return v


class Message(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    citations: Optional[list[dict]] = None
    settings_delta: Optional[dict] = None
    status: str = "complete"
    tokens: Optional[int] = None
    cost: Optional[float] = None
    created_at: datetime


class Thread(BaseModel):
    id: str
    owner_key: str
    title: Optional[str] = None
    settings: ThreadSettings
    created_at: datetime
    updated_at: datetime


class ThreadSummary(BaseModel):
    id: str
    title: Optional[str] = None
    last_activity_at: datetime
    message_count: int
