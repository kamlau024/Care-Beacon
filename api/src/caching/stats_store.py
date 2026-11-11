"""Redis-backed cumulative statistics.

Cost and usage counters must survive both process restarts and the many short-lived
instances a serverless deployment creates. A single Redis hash holds every counter;
readers fetch it in one round trip.

When no Redis client is available the store degrades to a silent no-op rather than
raising, so a cache outage never breaks the request path.
"""

from datetime import date, datetime, timezone
from typing import Dict, Optional

import redis
from redis.exceptions import RedisError

# Daily cost keys outlive their UTC day so late reads still work, then expire.
_DAILY_COST_TTL_SECONDS = 172_800


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

    def _daily_key(self, day: Optional[date]) -> str:
        day = day or datetime.now(timezone.utc).date()
        return f"{self._key_prefix}cost:{day.isoformat()}"

    def incr_daily_cost(self, amount: float, day: Optional[date] = None) -> None:
        """Add to the per-UTC-day cost counter (a separate string key with a TTL)."""
        if self.client is None:
            return
        key = self._daily_key(day)
        try:
            self.client.incrbyfloat(key, amount)
            self.client.expire(key, _DAILY_COST_TTL_SECONDS)
        except RedisError:
            pass

    def get_daily_cost(self, day: Optional[date] = None) -> Optional[float]:
        """Read the day's cost.

        Returns:
            Dollars spent (0.0 if nothing recorded yet), or None when Redis is
            unavailable or the stored value is unreadable.
        """
        if self.client is None:
            return None
        try:
            raw = self.client.get(self._daily_key(day))
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
