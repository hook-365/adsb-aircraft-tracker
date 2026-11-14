"""Watched aircraft: a user's own list of tail numbers, hex codes or callsigns.

Pure Python (no Home Assistant imports) so it can be exercised standalone.
"""
from __future__ import annotations

import re
from typing import Any

_SPLIT_RE = re.compile(r"[,;\s]+")
_NOISE_RE = re.compile(r"[^A-Z0-9]")

# Aircraft fields an entry is compared with, in the order they are tried
MATCH_FIELDS = ("hex", "tail", "flight")


def _key(value: Any) -> str:
    """Comparison form: upper case, letters and digits only (D-AIMA == daima)."""
    return _NOISE_RE.sub("", str(value or "").upper())


def entries(text: str | None) -> list[str]:
    """The list as typed, split on commas, semicolons, spaces or new lines.

    Upper-cased, duplicates dropped, order kept.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in _SPLIT_RE.split(text or ""):
        entry = raw.strip().upper()
        key = _key(entry)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def clean(text: str | None) -> str:
    """Tidy form of the list for storing and showing again."""
    return ", ".join(entries(text))


def keys(text: str | None) -> frozenset[str]:
    """Comparison keys for every entry of the list."""
    return frozenset(_key(entry) for entry in entries(text))


def match(aircraft: dict[str, Any], watched: frozenset[str]) -> bool:
    """True when the aircraft's hex code, tail number or callsign is on the list."""
    if not watched:
        return False
    for field in MATCH_FIELDS:
        value = aircraft.get(field)
        if field == "tail" and value == "Unknown":
            continue
        key = _key(value)
        if key and key in watched:
            return True
    return False
