"""Redis-backed cumulative statistics.

Cost and usage counters must survive both process restarts and the many short-lived
instances a serverless deployment creates. A single Redis hash holds every counter;
readers fetch it in one round trip.

When no Redis client is available the store degrades to a silent no-op rather than
raising, so a cache outage never breaks the request path.
"""

from typing import Dict, Optional

import redis
from redis.exceptions import RedisError


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
