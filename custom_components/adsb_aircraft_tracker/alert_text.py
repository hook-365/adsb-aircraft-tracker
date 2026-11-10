"""Custom wording for notifications: templates with {tokens}.

Pure Python (no Home Assistant imports) so it can be exercised standalone.
"""
from __future__ import annotations

import re

# token -> what it stands for (shown in the options dialog and the README)
TOKENS: dict[str, str] = {
    "name": "callsign, or the tail number when there is no callsign",
    "flight": "callsign",
    "tail": "tail number / registration",
    "hex": "ICAO hex code",
    "type": "aircraft type, e.g. Boeing 737-800",
    "operator": "owner or operator",
    "altitude": "altitude in feet, e.g. 3,000",
    "speed": "ground speed in knots",
    "distance": "distance from home with its unit, e.g. 1.4 mi",
    "direction": "where it is from home, e.g. northwest",
    "heading": "where it is going, e.g. south",
    "trend": "↗️ climbing, ↘️ descending, → level",
    "emoji": "icon for the alert or aircraft (🚁 🛫 🛬 🛩️ ✈️ 🪖 ⬆️ ⚠️)",
    "angle": "degrees from straight up (overhead alert)",
    "where": "e.g. \"13° from straight up\" (overhead alert)",
    "squawk": "squawk code (emergency alert)",
    "emergency": "GENERAL EMERGENCY, RADIO FAILURE or HIJACK (emergency alert)",
    "reasons": "why it was flagged (military alert)",
}

# Templates that reproduce the built-in wording; the options dialog is
# pre-filled with these
DEFAULTS: dict[str, tuple[str, str]] = {
    "military": (
        "🪖 MILITARY AIRCRAFT DETECTED",
        "🪖 {name} at {altitude}ft {trend} {distance} away\nType: {type}\nSpeed: {speed}kts\nCallsign: {flight}\nDetected by: {reasons}",
    ),
    "close_aircraft": (
        "✈️ LOW AIRCRAFT OVERHEAD",
        "{emoji} {name} at {altitude}ft {trend} {distance} away\n{type} • {speed}kts\nFlight: {flight}\nOperator: {operator}",
    ),
    "overhead": (
        "⬆️ AIRCRAFT OVERHEAD",
        "⬆️ {name} at {altitude}ft, {where}\n{type} • {speed}kts heading {heading}\nOperator: {operator}",
    ),
    "emergency": (
        "⚠️ EMERGENCY SQUAWK",
        "{name} squawking {squawk} ({emergency}) at {distance}",
    ),
}

_TOKEN_RE = re.compile(r"\{([a-z_]+)\}")


def render(template: str | None, values: dict[str, str]) -> str:
    """Fill {tokens} in a template. Empty result means "use the built-in text".

    Unknown tokens are left as typed. A line whose tokens all came out empty
    is dropped, so "Operator: {operator}" disappears for an aircraft with no
    known operator instead of leaving a dangling label.
    """
    if not template or not template.strip():
        return ""
    lines = []
    for line in template.replace("\\n", "\n").splitlines():
        known = filled = 0

        def fill(match: re.Match[str]) -> str:
            nonlocal known, filled
            key = match.group(1)
            if key not in values:
                return match.group(0)
            known += 1
            value = str(values[key] or "").strip()
            if value:
                filled += 1
            return value

        text = _TOKEN_RE.sub(fill, line)
        if known and not filled:
            continue
        lines.append(text.rstrip())
    return "\n".join(lines).strip()
