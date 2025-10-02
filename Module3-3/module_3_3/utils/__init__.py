"""Utility helpers for the Module3-3 ruleset compiler."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Mapping


def sha256_digest(payload: bytes) -> str:
    """Return the hex encoded SHA-256 digest for *payload*."""

    return hashlib.sha256(payload).hexdigest()


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(tz=timezone.utc)


def ensure_allowed_scope(scope: Mapping[str, object]) -> None:
    """Raise ValueError if *scope* references unsupported keys."""

    allowed = {"category", "subcategory", "canonical_terms", "normalized_text", "def_bindings"}
    unknown = set(scope) - allowed
    if unknown:
        raise ValueError(f"Unsupported scope keys: {sorted(unknown)}")
