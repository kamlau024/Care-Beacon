"""Request/response models for the thread endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.chat.models import Message, ThreadSettings, ThreadSummary

MAX_TITLE_LENGTH = 200
MIN_MESSAGE_LENGTH = 3
MAX_MESSAGE_LENGTH = 500


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


class ChatRequest(BaseModel):
    """One chat turn. ``settings`` applies only when creating a thread."""

    thread_id: Optional[str] = None
    message: str = Field(min_length=MIN_MESSAGE_LENGTH, max_length=MAX_MESSAGE_LENGTH)
    settings: Optional[ThreadSettings] = None
    include_full_text: bool = False
