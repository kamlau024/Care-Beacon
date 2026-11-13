"""In-memory test doubles."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from src.chat.models import Message, Thread, ThreadSettings, ThreadSummary
from src.chat.repository import ThreadNotFound, new_message_id, new_thread_id


class InMemoryThreadRepository:
    """Same public surface and ownership semantics as ThreadRepository."""

    def __init__(self):
        self._threads: dict[str, Thread] = {}
        self._messages: dict[str, list[Message]] = {}
        self._last = datetime.min.replace(tzinfo=timezone.utc)

    def _now(self) -> datetime:
        # Strictly increasing so ordering never depends on clock resolution.
        now = max(datetime.now(timezone.utc), self._last + timedelta(microseconds=1))
        self._last = now
        return now

    def _owned(self, thread_id: str, owner_key: str) -> Optional[Thread]:
        t = self._threads.get(thread_id)
        return t if t is not None and t.owner_key == owner_key else None

    def create_thread(self, owner_key: str, settings: ThreadSettings) -> Thread:
        now = self._now()
        t = Thread(
            id=new_thread_id(),
            owner_key=owner_key,
            title=None,
            settings=settings.model_copy(deep=True),
            created_at=now,
            updated_at=now,
        )
        self._threads[t.id] = t
        self._messages[t.id] = []
        return t.model_copy(deep=True)

    def get_thread(self, thread_id: str, owner_key: str) -> Optional[Thread]:
        t = self._owned(thread_id, owner_key)
        return t.model_copy(deep=True) if t else None

    def list_threads(self, owner_key: str) -> list[ThreadSummary]:
        out = []
        for t in self._threads.values():
            msgs = self._messages[t.id]
            if t.owner_key != owner_key:
                continue
            last = max((m.created_at for m in msgs), default=t.created_at)
            out.append(
                ThreadSummary(
                    id=t.id, title=t.title, last_activity_at=last, message_count=len(msgs)
                )
            )
        return sorted(out, key=lambda s: s.last_activity_at, reverse=True)

    def list_messages(self, thread_id: str) -> list[Message]:
        return [m.model_copy(deep=True) for m in self._messages.get(thread_id, [])]

    def _add_message(self, thread_id, role, content, citations, settings_delta,
                     status, tokens, cost) -> Message:
        now = self._now()
        m = Message(
            id=new_message_id(),
            thread_id=thread_id,
            role=role,
            content=content,
            citations=citations,
            settings_delta=settings_delta,
            status=status,
            tokens=tokens,
            cost=cost,
            created_at=now,
        )
        self._messages[thread_id].append(m)
        self._threads[thread_id].updated_at = now
        return m

    def append_message(self, thread_id: str, role: str, content: str, *,
                       citations=None, settings_delta=None, status="complete",
                       tokens=None, cost=None) -> Message:
        if thread_id not in self._threads:
            raise ThreadNotFound(thread_id)
        m = self._add_message(thread_id, role, content, citations, settings_delta,
                              status, tokens, cost)
        return m.model_copy(deep=True)

    def rename_thread(self, thread_id: str, owner_key: str, title: str) -> bool:
        t = self._owned(thread_id, owner_key)
        if t is None:
            return False
        t.title = title
        return True

    def set_title_if_empty(self, thread_id: str, title: str) -> None:
        t = self._threads.get(thread_id)
        if t is not None and t.title is None:
            t.title = title

    def delete_thread(self, thread_id: str, owner_key: str) -> bool:
        if self._owned(thread_id, owner_key) is None:
            return False
        del self._threads[thread_id]
        del self._messages[thread_id]
        return True

    def update_settings(self, thread_id: str, owner_key: str,
                        settings: ThreadSettings) -> Optional[Message]:
        t = self._owned(thread_id, owner_key)
        if t is None:
            raise ThreadNotFound(thread_id)
        if t.settings == settings:
            return None
        delta = {"before": t.settings.model_dump(), "after": settings.model_dump()}
        t.settings = settings.model_copy(deep=True)
        m = self._add_message(thread_id, "settings", "", None, delta, "complete", None, None)
        return m.model_copy(deep=True)
