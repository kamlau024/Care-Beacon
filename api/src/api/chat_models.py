"""Request/response models for the thread endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from src.chat.models import Message, ThreadSettings, ThreadSummary

MAX_TITLE_LENGTH = 200


class ThreadListResponse(BaseModel):
    threads: list[ThreadSummary]


class ThreadDetailResponse(BaseModel):
    id: str
    title: Optional[str] = None
    settings: ThreadSettings
    messages: list[Message]


class RenameRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        v = v.strip()[:MAX_TITLE_LENGTH].strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class RenameResponse(BaseModel):
    id: str
    title: str


class OkResponse(BaseModel):
    ok: bool = True


class SettingsResponse(BaseModel):
    settings: ThreadSettings
    marker: Optional[Message] = None
