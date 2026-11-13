"""Daily spend cap for the public chat endpoint."""

from loguru import logger

from src.caching.stats_store import StatsStore
from src.config_loader import get_config

_DEFAULT_CAP_USD = 2.0


def daily_cap_usd() -> float:
    """Return the configured per-UTC-day spend cap in dollars."""
    return float(get_config().get("chat.daily_spend_cap_usd", _DEFAULT_CAP_USD))


def cap_reached(stats_store: StatsStore) -> bool:
    """True when today's (UTC) spend is at or above the cap.

    Fails open: if the day's cost can't be read, logs a warning and returns False.
    """
    cost = stats_store.get_daily_cost()
    if cost is None:
        logger.warning("Daily spend cap check skipped: today's cost is unavailable")
        return False
    return cost >= daily_cap_usd()
