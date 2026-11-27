"""Redis-backed cumulative statistics.

Cost and usage counters must survive both process restarts and the many short-lived
instances a serverless deployment creates. A single Redis hash holds every counter;
readers fetch it in one round trip.

When no Redis client is available the store degrades to a silent no-op rather than
raising, so a cache outage never breaks the request path.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timezone
from typing import Dict, Iterator, Optional

import redis
from redis.exceptions import RedisError

# Daily cost keys outlive their UTC day so late reads still work, then expire.
_DAILY_COST_TTL_SECONDS = 172_800

# Which channel the current request's spend belongs to (e.g. "mcp"), or None.
# Cost is recorded deep inside the embedding and LLM clients, so the request
# sets this once instead of threading a parameter through every layer. A
# ContextVar follows the request into anyio.to_thread worker threads.
_spend_channel: ContextVar[Optional[str]] = ContextVar("spend_channel", default=None)


@contextmanager
def spend_channel(name: str) -> Iterator[None]:
    """Also count spend recorded inside this block toward channel `name`."""
    token = _spend_channel.set(name)
    try:
        yield
    finally:
        _spend_channel.reset(token)


class StatsStore:
    """Cumulative counters held in one Redis hash."""

    def __init__(self, client: Optional["redis.Redis"], key_prefix: str = "care_beacon:") -> None:
        """Initialise the store.

        Args:
            client: Connected Redis client, or None to disable persistence.
            key_prefix: Prefix shared with the rest of the cache keyspace.
        """
        self.client = client
        self.key = f"{key_prefix}stats"
        self._key_prefix = key_prefix

    def incr(self, field: str, amount: int = 1) -> None:
        """Add to an integer counter."""
        if self.client is None:
            return
        try:
            self.client.hincrby(self.key, field, amount)
        except RedisError:
            pass

    def incr_float(self, field: str, amount: float) -> None:
        """Add to a floating-point counter."""
        if self.client is None:
            return
        try:
            self.client.hincrbyfloat(self.key, field, amount)
        except RedisError:
            pass

    def _daily_key(self, day: Optional[date], channel: Optional[str] = None) -> str:
        day = day or datetime.now(timezone.utc).date()
        key = f"{self._key_prefix}cost:{day.isoformat()}"
        return f"{key}:{channel}" if channel else key

    def incr_daily_cost(self, amount: float, day: Optional[date] = None) -> None:
        """Add to the per-UTC-day cost counter (a separate string key with a TTL).

        Inside `spend_channel(name)`, the amount is also added to that channel's
        own daily counter. The total always includes every channel.
        """
        if self.client is None:
            return
        keys = [self._daily_key(day)]
        channel = _spend_channel.get()
        if channel:
            keys.append(self._daily_key(day, channel))
        try:
            for key in keys:
                self.client.incrbyfloat(key, amount)
                self.client.expire(key, _DAILY_COST_TTL_SECONDS)
        except RedisError:
            pass

    def get_daily_cost(
        self, day: Optional[date] = None, channel: Optional[str] = None
    ) -> Optional[float]:
        """Read the day's cost: the total, or one channel's share.

        Returns:
            Dollars spent (0.0 if nothing recorded yet), or None when Redis is
            unavailable or the stored value is unreadable.
        """
        if self.client is None:
            return None
        try:
            raw = self.client.get(self._daily_key(day, channel))
            return 0.0 if raw is None else float(raw)
        except (RedisError, ValueError):
            return None

    def get_all(self) -> Dict[str, float]:
        """Read every counter.

        Returns:
            Field name to value. Empty when Redis is unavailable, or when a
            stored value can't be parsed as a number.
        """
        if self.client is None:
            return {}
        try:
            raw = self.client.hgetall(self.key)
            return {k: float(v) for k, v in raw.items()}
        except (RedisError, ValueError):
            return {}

    def reset(self) -> None:
        """Delete every counter."""
        if self.client is None:
            return
        try:
            self.client.delete(self.key)
        except RedisError:
            pass
