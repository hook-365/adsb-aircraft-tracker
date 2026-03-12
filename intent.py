"""Intent handlers for ADSB Aircraft Tracker voice support."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN
from .coordinator import ADSBDataUpdateCoordinator
from .route_client import RouteClient, RouteInfo

_LOGGER = logging.getLogger(__name__)

INTENT_WHAT_PLANE = "ADSBWhatPlane"
INTENT_NEAREST_AIRCRAFT = "ADSBNearestAircraft"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Register ADSB intent handlers with Home Assistant."""
    intent.async_register(hass, WhatPlaneIntentHandler())
    intent.async_register(hass, NearestAircraftIntentHandler())
    _LOGGER.info("Registered ADSB voice intent handlers")


class WhatPlaneIntentHandler(intent.IntentHandler):
    """Handler for 'what plane is that' style queries."""

    intent_type = INTENT_WHAT_PLANE
    description = "Identifies the closest aircraft overhead with route information"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        response = intent_obj.create_response()

        coordinator, route_client = _get_best_coordinator(hass)
        if coordinator is None:
            response.async_set_speech(
                "I don't have any aircraft data right now."
            )
            return response

        aircraft_list = coordinator.data.get("aircraft", [])
        if not aircraft_list:
            response.async_set_speech("No planes are nearby right now.")
            return response

        aircraft = dict(aircraft_list[0])
        route = await _fetch_route_for_aircraft(aircraft, route_client)

        speech = _format_aircraft_response(aircraft, route, coordinator)
        response.async_set_speech(speech)
        return response


class NearestAircraftIntentHandler(intent.IntentHandler):
    """Handler for 'what aircraft are nearby' style queries."""

    intent_type = INTENT_NEAREST_AIRCRAFT
    description = "Lists the nearest aircraft currently tracked"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        response = intent_obj.create_response()

        coordinator, route_client = _get_best_coordinator(hass)
        if coordinator is None:
            response.async_set_speech("No aircraft data available right now.")
            return response

        aircraft_list = coordinator.data.get("aircraft", [])
        if not aircraft_list:
            response.async_set_speech("No aircraft are being tracked right now.")
            return response

        nearest = [a for a in aircraft_list[:3] if a.get("distance_mi") is not None]
        if not nearest:
            count = len(aircraft_list)
            response.async_set_speech(
                f"There are {count} aircraft being tracked but none have position data."
            )
            return response

        parts = []
        for aircraft in nearest:
            identity = _get_identity(aircraft)
            dist = coordinator.format_distance(aircraft.get("distance_mi"))
            alt = aircraft.get("altitude_ft")
            alt_str = f" at {alt:,} feet" if alt else ""
            dist_str = f", {dist} away" if dist and dist != "Unknown" else ""
            parts.append(f"{identity}{dist_str}{alt_str}")

        count = len(aircraft_list)
        summary = (
            f"I'm tracking {count} aircraft. The nearest are: "
            + "; ".join(parts)
            + "."
        )
        response.async_set_speech(summary)
        return response


def _get_best_coordinator(
    hass: HomeAssistant,
) -> tuple[ADSBDataUpdateCoordinator | None, RouteClient | None]:
    """Find the coordinator with the closest aircraft data."""
    if DOMAIN not in hass.data:
        return None, None

    best_coordinator = None
    best_route_client = None
    best_distance = float("inf")

    for entry_data in hass.data[DOMAIN].values():
        if not isinstance(entry_data, dict):
            continue
        coordinator = entry_data.get("coordinator")
        if not coordinator or not coordinator.data:
            continue
        aircraft_list = coordinator.data.get("aircraft", [])
        if not aircraft_list:
            continue

        distance = aircraft_list[0].get("distance_mi") or float("inf")
        if distance < best_distance:
            best_distance = distance
            best_coordinator = coordinator
            best_route_client = entry_data.get("route_client")

    return best_coordinator, best_route_client


async def _fetch_route_for_aircraft(
    aircraft: dict[str, Any],
    route_client: RouteClient | None,
) -> RouteInfo:
    """Fetch route for an aircraft's callsign."""
    callsign = aircraft.get("flight")
    if not callsign or not route_client:
        return RouteInfo(callsign=callsign or "", valid=False)
    return await route_client.async_get_route(callsign)


def _get_identity(aircraft: dict[str, Any]) -> str:
    """Return the best human-readable identity for an aircraft."""
    flight = aircraft.get("flight")
    operator = aircraft.get("operator")
    if flight and operator:
        return f"{operator} {flight}"
    if flight:
        return flight
    tail = aircraft.get("tail")
    if tail:
        return tail
    return "an unidentified aircraft"


def _format_aircraft_response(
    aircraft: dict[str, Any],
    route: RouteInfo,
    coordinator: ADSBDataUpdateCoordinator,
) -> str:
    """Build a natural language description of an aircraft."""
    identity = _get_identity(aircraft)
    description = aircraft.get("description", "")
    distance_mi = aircraft.get("distance_mi")
    altitude_ft = aircraft.get("altitude_ft")

    parts = [f"That's {identity}"]

    if description:
        parts[0] += f", a {description}"

    if route.valid and route.origin_name and route.destination_name:
        parts.append(f"flying from {route.origin_name} to {route.destination_name}")

    if distance_mi is not None:
        dist_str = coordinator.format_distance(distance_mi)
        if dist_str and dist_str != "Unknown":
            parts.append(f"about {dist_str} away")

    if altitude_ft and isinstance(altitude_ft, (int, float)) and altitude_ft > 0:
        parts.append(f"at {int(altitude_ft):,} feet")

    return ", ".join(parts) + "."
