"""Thread REST endpoints (list, open, rename, delete, settings)."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.chat_models import (
    OkResponse,
    RenameRequest,
    RenameResponse,
    SettingsResponse,
    ThreadDetailResponse,
    ThreadListResponse,
)
from src.chat.models import ThreadSettings
from src.chat.repository import ThreadNotFound, ThreadRepository
from src.db.connection import DatabaseUnavailable, connect

_OWNER_KEY_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

router = APIRouter(prefix="/api/v1", tags=["Chat"])


def require_owner_key(
    x_owner_key: str | None = Header(None, alias="X-Owner-Key"),
) -> str:
    if not x_owner_key or not _OWNER_KEY_RE.match(x_owner_key):
        raise HTTPException(status_code=400, detail="Missing or invalid X-Owner-Key header")
    return x_owner_key


def get_repository() -> ThreadRepository:
    return ThreadRepository(connect=connect)


async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable):
    # Deliberately generic: never echo the exception text.
    return JSONResponse(
        status_code=503,
        content={
            "error": "ServiceUnavailable",
            "message": "Conversation storage is temporarily unavailable",
            "timestamp": datetime.now().isoformat(),
        },
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Thread not found")


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    owner: str = Depends(require_owner_key),
    repo: ThreadRepository = Depends(get_repository),
):
    return ThreadListResponse(threads=repo.list_threads(owner))


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
def get_thread(
    thread_id: str,
    owner: str = Depends(require_owner_key),
    repo: ThreadRepository = Depends(get_repository),
):
    thread = repo.get_thread(thread_id, owner)
    if thread is None:
        raise _not_found()
    return ThreadDetailResponse(
        id=thread.id,
        title=thread.title,
        settings=thread.settings,
        messages=repo.list_messages(thread.id),
    )


@router.patch("/threads/{thread_id}", response_model=RenameResponse)
def rename_thread(
    thread_id: str,
    body: RenameRequest,
    owner: str = Depends(require_owner_key),
    repo: ThreadRepository = Depends(get_repository),
):
    if not repo.rename_thread(thread_id, owner, body.title):
        raise _not_found()
    return RenameResponse(id=thread_id, title=body.title)


@router.delete("/threads/{thread_id}", response_model=OkResponse)
def delete_thread(
    thread_id: str,
    owner: str = Depends(require_owner_key),
    repo: ThreadRepository = Depends(get_repository),
):
    if not repo.delete_thread(thread_id, owner):
        raise _not_found()
    return OkResponse()


@router.patch("/threads/{thread_id}/settings", response_model=SettingsResponse)
def update_thread_settings(
    thread_id: str,
    settings: ThreadSettings,
    owner: str = Depends(require_owner_key),
    repo: ThreadRepository = Depends(get_repository),
):
    try:
        marker = repo.update_settings(thread_id, owner, settings)
    except ThreadNotFound:
        raise _not_found()
    return SettingsResponse(settings=settings, marker=marker)
