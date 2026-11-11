"""Helpers for validating and normalizing request filters."""

from typing import List, Optional, Union

from src.config_loader import get_config


def configured_sources() -> List[str]:
    """Valid `source` filter values, in configured order."""
    return list(get_config().get("retrieval.sources", []))


def normalize_sources(
    source: Union[str, List[str], None], configured: List[str]
) -> Union[str, List[str], None]:
    """Normalize a source filter.

    Returns None for no filter (nothing given, or every configured source),
    the bare string for exactly one source, and a de-duplicated list in
    configured order for two or more. Raises ValueError on unknown sources.
    """
    if source is None:
        return None
    requested = [source] if isinstance(source, str) else list(source)
    if not requested:
        return None

    unknown = [s for s in dict.fromkeys(requested) if s not in configured]
    if unknown:
        raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

    selected = [s for s in configured if s in requested]
    if len(selected) == len(configured):
        return None
    if len(selected) == 1:
        return selected[0]
    return selected
