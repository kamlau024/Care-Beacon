"""Static bearer keys for /api/mcp (development, evals and smoke tests).

MCP_API_KEYS holds comma-separated ``name:sha256hex`` pairs, so raw keys never
sit in the environment and each client has its own revocable name. The name,
never the key, is what traces and rate limits see. OAuth (Phase 2) replaces
these for the public.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Dict, Optional, Tuple

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_keys(raw: Optional[str]) -> Dict[str, str]:
    """Parse MCP_API_KEYS into {name: sha256hex}. Malformed entries are skipped."""
    keys: Dict[str, str] = {}
    for entry in (raw or "").split(","):
        name, sep, digest = entry.strip().partition(":")
        name, digest = name.strip(), digest.strip().lower()
        if sep and _NAME.match(name) and _HEX64.match(digest):
            keys[name] = digest
    return keys


def authenticate(authorization: Optional[str], keys: Dict[str, str]) -> Optional[str]:
    """Return the key's name for a valid ``Authorization: Bearer <key>``, else None.

    Compares against every entry with hmac.compare_digest, so timing doesn't
    reveal which entry (if any) was close.
    """
    if not authorization or not keys:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    digest = _sha256(token)
    match = None
    for name, expected in keys.items():
        if hmac.compare_digest(digest, expected):
            match = name
    return match


def make_key(name: str) -> Tuple[str, str]:
    """Generate a key for `name`. Returns (raw key, the ``name:sha256`` env line)."""
    if not _NAME.match(name or ""):
        raise ValueError("Key name may contain only letters, digits, '.', '_' and '-'")
    raw = secrets.token_urlsafe(32)
    return raw, f"{name}:{_sha256(raw)}"
