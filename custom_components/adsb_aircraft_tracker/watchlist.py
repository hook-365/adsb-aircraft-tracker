"""Watched aircraft: a user's own list of aircraft to be alerted about.

Three lists: tail numbers / hex codes / callsigns, ICAO type codes, and
operator names. Pure Python (no Home Assistant imports) so it can be
exercised standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any

_SPLIT_RE = re.compile(r"[,;\s]+")
# Operator names contain spaces, so only these separate them
_NAME_SPLIT_RE = re.compile(r"[,;\n]+")
_NOISE_RE = re.compile(r"[^A-Z0-9]")
_TYPE_NOISE_RE = re.compile(r"[^A-Z0-9*]")

# Aircraft fields an entry is compared with, in the order they are tried
MATCH_FIELDS = ("hex", "tail", "flight")
# An operator entry shorter than this would match nearly everything
MIN_OPERATOR_LENGTH = 2


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


def type_entries(text: str | None) -> list[str]:
    """ICAO type codes as typed: upper case, `*` kept as the wildcard.

    A lone `*` is dropped: it would put every aircraft on the list.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in _SPLIT_RE.split(text or ""):
        entry = _TYPE_NOISE_RE.sub("", raw.upper())
        if not entry.strip("*") or entry in seen:
            continue
        seen.add(entry)
        result.append(entry)
    return result


def clean_types(text: str | None) -> str:
    """Tidy form of the type list for storing and showing again."""
    return ", ".join(type_entries(text))


def operator_entries(text: str | None) -> list[str]:
    """Operator names as typed, split on commas, semicolons or new lines.

    Spaces inside a name are kept; duplicates (ignoring case and
    punctuation) and entries too short to mean anything are dropped.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in _NAME_SPLIT_RE.split(text or ""):
        entry = " ".join(raw.split())
        key = _key(entry)
        if len(key) < MIN_OPERATOR_LENGTH or key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def clean_operators(text: str | None) -> str:
    """Tidy form of the operator list for storing and showing again."""
    return ", ".join(operator_entries(text))


@dataclass(frozen=True)
class Watch:
    """The three lists in comparison form. Falsy when all are empty."""

    ids: frozenset[str] = frozenset()
    types: tuple[str, ...] = ()
    operators: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.ids or self.types or self.operators)


def build(
    ids: str | None = None, types: str | None = None, operators: str | None = None
) -> Watch:
    """Comparison form of the lists as stored."""
    return Watch(
        ids=keys(ids),
        types=tuple(type_entries(types)),
        operators=tuple(_key(entry) for entry in operator_entries(operators)),
    )


def match(aircraft: dict[str, Any], watch: Watch) -> str | None:
    """Why the aircraft is on the list, or None when it is not.

    "hex", "tail" or "flight" for an entry of the main list, "type" for a
    type code, "operator" for an operator name.
    """
    if not watch:
        return None
    for field in MATCH_FIELDS:
        value = aircraft.get(field)
        if field == "tail" and value == "Unknown":
            continue
        key = _key(value)
        if key and key in watch.ids:
            return field
    type_code = _key(aircraft.get("aircraft_type"))
    if type_code and any(fnmatchcase(type_code, pattern) for pattern in watch.types):
        return "type"
    operator = _key(aircraft.get("operator"))
    if operator and operator != "UNKNOWN" and any(
        entry in operator for entry in watch.operators
    ):
        return "operator"
    return None
