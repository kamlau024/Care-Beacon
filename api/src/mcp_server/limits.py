"""Abuse protection for /api/mcp: per-caller rate limits and the MCP spend cap.

Both fail closed. The endpoint is public, and an agent stuck in a loop is the
likeliest way to burn the budget, so when Redis can't be read the call is
refused rather than allowed (Chat's cap, by contrast, fails open).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger
from redis.exceptions import RedisError

from src.caching.stats_store import StatsStore
from src.config_loader import get_config

MCP_CHANNEL = "mcp"

_MINUTE = 60
_DAY = 86_400


@dataclass(frozen=True)
class McpSettings:
    daily_spend_cap_usd: float
    per_minute: int
    per_day: int


def load_settings() -> McpSettings:
    """Read the `mcp` block of config.yaml.

    MCP_DAILY_SPEND_CAP_USD and MCP_RATE_LIMIT_PER_MIN override it only outside
    production (so previews and evals can force the cap or limit errors).
    """
    config = get_config()
    cap = float(config.get("mcp.daily_spend_cap_usd", 2.0))
    per_minute = int(config.get("mcp.rate_limit.per_minute", 10))
    per_day = int(config.get("mcp.rate_limit.per_day", 50))
    if os.getenv("VERCEL_ENV") != "production":
        if os.getenv("MCP_DAILY_SPEND_CAP_USD"):
            cap = float(os.environ["MCP_DAILY_SPEND_CAP_USD"])
        if os.getenv("MCP_RATE_LIMIT_PER_MIN"):
            per_minute = int(os.environ["MCP_RATE_LIMIT_PER_MIN"])
    return McpSettings(daily_spend_cap_usd=cap, per_minute=per_minute, per_day=per_day)


def mcp_cap_reached(stats_store: StatsStore, *, cap_usd: float) -> bool:
    """True when today's MCP spend is at or above the cap, or can't be read."""
    cost = stats_store.get_daily_cost(channel=MCP_CHANNEL)
    if cost is None:
        logger.warning("MCP spend counter unreadable: refusing the call (fail closed)")
        return True
    return cost >= cap_usd


class RateLimiter:
    """Fixed-window counters in Redis, per caller: one per minute, one per UTC day."""

    def __init__(
        self,
        client: Optional[Any],
        *,
        per_minute: int,
        per_day: int,
        key_prefix: str = "care_beacon:",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client = client
        self.per_minute = per_minute
        self.per_day = per_day
        self.prefix = f"{key_prefix}mcp:rl"
        self.clock = clock

    def _count(self, key: str, ttl: int) -> int:
        n = self.client.incr(key)
        if n == 1:
            self.client.expire(key, ttl)
        return n

    def check(self, caller: str) -> Optional[int]:
        """Count one call. Returns None if allowed, else seconds until it would be."""
        now = self.clock()
        minute, day = int(now // _MINUTE), int(now // _DAY)
        if self.client is None:
            return _MINUTE
        try:
            per_minute = self._count(f"{self.prefix}:{caller}:m:{minute}", 2 * _MINUTE)
            per_day = self._count(f"{self.prefix}:{caller}:d:{day}", 2 * _DAY)
        except RedisError:
            logger.warning("MCP rate limiter unavailable: refusing the call (fail closed)")
            return _MINUTE
        if per_day > self.per_day:
            return _DAY - int(now - day * _DAY)
        if per_minute > self.per_minute:
            return _MINUTE - int(now - minute * _MINUTE)
        return None
