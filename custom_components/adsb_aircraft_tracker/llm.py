"""LLM tools platform for ADSB Aircraft Tracker.

Since HA 2026.8 intents are no longer auto-exposed to LLM conversation agents:
each integration must ship an ``llm.py`` platform that returns its tools for
the Assist API. Without this file the ADSB intents only work through the local
sentence-trigger path, and an LLM agent falls back to GetLiveContext on the
exposed summary sensor (which is how "nearest plane" degraded to a bare tail
number on 2026-09-01).

The tools wrap the existing intent handlers (so the spoken answer is identical
to the local path) but carry much richer descriptions so the model picks the
right one.
"""

from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool

from .intent import (
    INTENT_AIRCRAFT_BY_TYPE,
    INTENT_AIRCRAFT_COUNT,
    INTENT_AIRCRAFT_ROUTE,
    INTENT_AIRCRAFT_SUPERLATIVE,
    INTENT_MILITARY_STATUS,
    INTENT_NEAREST_AIRCRAFT,
    INTENT_WHAT_PLANE,
)

# Descriptions the model sees. Written for tool selection, not for humans.
TOOL_DESCRIPTIONS: dict[str, str] = {
    INTENT_WHAT_PLANE: (
        "Identify the single closest aircraft overhead right now: operator or "
        "airline, aircraft type, distance, altitude and climb or descent, "
        "heading, speed, and route when known. Use for 'what plane is that', "
        "'what's flying over', 'what is the nearest plane', 'what's that jet'. "
        "No arguments. Returns ready-to-speak text in 'speech'."
    ),
    INTENT_NEAREST_AIRCRAFT: (
        "List the three nearest aircraft with operator, distance, altitude and "
        "heading, plus the total count being tracked. Use for 'what planes are "
        "nearby', 'what's in the air around us', 'list the closest planes'. "
        "No arguments."
    ),
    INTENT_MILITARY_STATUS: (
        "Report whether any military aircraft are currently being tracked and "
        "describe them. Use for any question mentioning military, air force, "
        "army, navy, fighter, tanker, or 'anything interesting up there'. "
        "No arguments."
    ),
    INTENT_AIRCRAFT_COUNT: (
        "Report how many aircraft are currently being tracked and how far the "
        "closest one is. Use for 'how many planes', 'how busy is the sky'. "
        "No arguments."
    ),
    INTENT_AIRCRAFT_ROUTE: (
        "Report where the closest aircraft is flying from and to. Use for "
        "'where is that plane going', 'where did it come from', 'what route'. "
        "No arguments."
    ),
    INTENT_AIRCRAFT_BY_TYPE: (
        "Find nearby aircraft of a given kind. 'type' is a word like "
        "helicopter, jet, prop, airliner, business jet, cargo, drone. Use for "
        "'any helicopters around', 'is there a jet nearby'."
    ),
    INTENT_AIRCRAFT_SUPERLATIVE: (
        "Find the fastest, slowest, highest, lowest, closest, or farthest "
        "aircraft currently tracked. 'query' is the superlative word. Use for "
        "'what's the highest plane', 'fastest aircraft right now'."
    ),
}

AIRCRAFT_PROMPT = (
    "For ANY question about planes, aircraft, jets, helicopters, flights, or "
    "what is flying over, call one of the ADSB tools (ADSBWhatPlane is the "
    "default for 'what plane is that' or 'nearest plane'). Do not use "
    "GetLiveContext or sensor states for aircraft questions. Each ADSB tool "
    "returns a 'speech' string already written for text to speech: read it "
    "back nearly word for word, including operator, aircraft type, distance, "
    "altitude and heading. Never answer with only a tail number or callsign."
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the ADSB intent tools for the Assist API."""
    if api_id != LLM_API_ASSIST:
        return None

    tools: list[Tool] = []
    for handler in intent.async_get(hass):
        if handler.intent_type not in TOOL_DESCRIPTIONS:
            continue
        tool = IntentTool(handler.intent_type, handler)
        tool.description = TOOL_DESCRIPTIONS[handler.intent_type]
        tools.append(tool)

    if not tools:
        return None
    return LLMTools(tools=tools, prompt=AIRCRAFT_PROMPT)
