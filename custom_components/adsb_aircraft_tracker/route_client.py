"""Route lookup client for ADSB Aircraft Tracker."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .geo import angle_between, distance_and_bearing

_LOGGER = logging.getLogger(__name__)

ROUTE_API_URL = "https://adsb.im/api/0/routeset"
ROUTE_CACHE_TTL = timedelta(hours=4)
ROUTE_API_TIMEOUT = 5
# Callsigns per routeset request when looking up routes in bulk
ROUTE_BATCH_SIZE = 100


@dataclass
class RouteInfo:
    """Route information for a flight."""

    callsign: str
    origin_iata: str | None = None
    origin_name: str | None = None
    destination_iata: str | None = None
    destination_name: str | None = None
    valid: bool = False
    # Every stop, in order: dicts with iata, name, lat, lon. Multi-stop
    # flights (e.g. MSP-CLE-MSP) need the current leg picked by position.
    airports: list[dict[str, Any]] = field(default_factory=list)

    def for_position(
        self, lat: float | None, lon: float | None, track: float | None
    ) -> RouteInfo:
        """Return this route narrowed to the leg the aircraft is flying now.

        Origin/destination default to the first and last stops, which is
        wrong for multi-stop flights (a round trip would read "MSP to MSP").
        With a position, pick the leg the aircraft is closest to lying on
        (least detour via its position), preferring legs whose next stop is
        roughly ahead of its track.
        """
        if not self.valid or len(self.airports) < 3 or lat is None or lon is None:
            return self
        best = None
        for start, end in zip(self.airports, self.airports[1:]):
            if None in (start.get("lat"), start.get("lon"), end.get("lat"), end.get("lon")):
                continue
            to_start, _ = distance_and_bearing(start["lat"], start["lon"], lat, lon)
            to_end, bearing_to_end = distance_and_bearing(lat, lon, end["lat"], end["lon"])
            leg, _ = distance_and_bearing(start["lat"], start["lon"], end["lat"], end["lon"])
            score = to_start + to_end - leg
            if isinstance(track, (int, float)) and angle_between(track, bearing_to_end) > 90:
                score += leg  # next stop is behind us: probably the other direction
            if best is None or score < best[0]:
                best = (score, start, end)
        if best is None:
            return self
        _, start, end = best
        return replace(
            self,
            origin_iata=start.get("iata"),
            origin_name=start.get("name"),
            destination_iata=end.get("iata"),
            destination_name=end.get("name"),
        )


class RouteClient:
    """Async client for fetching flight route data with TTL cache."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize route client."""
        self._hass = hass
        self._cache: dict[str, tuple[RouteInfo, datetime]] = {}

    def get_cached_route(self, callsign: str | None) -> RouteInfo | None:
        """Return an unexpired cached route without fetching, else None."""
        if not callsign:
            return None
        cached = self._cache.get(callsign.strip().upper())
        if cached and dt_util.utcnow() - cached[1] < ROUTE_CACHE_TTL:
            return cached[0]
        return None

    async def async_get_route(self, callsign: str) -> RouteInfo:
        """Fetch route for a callsign, using cache when available."""
        if not callsign:
            return RouteInfo(callsign="", valid=False)

        normalized = callsign.strip().upper()

        if normalized in self._cache:
            cached_route, cached_at = self._cache[normalized]
            if dt_util.utcnow() - cached_at < ROUTE_CACHE_TTL:
                return cached_route

        route = await self._async_fetch_route(normalized)
        now = dt_util.utcnow()
        # Drop expired entries so the cache can't grow without bound
        self._cache = {
            key: value
            for key, value in self._cache.items()
            if now - value[1] < ROUTE_CACHE_TTL
        }
        self._cache[normalized] = (route, now)
        return route

    async def async_get_routes(
        self, planes: list[tuple[str, float | None, float | None]]
    ) -> dict[str, RouteInfo]:
        """Look up routes for many (callsign, lat, lon) at once.

        Only callsigns without an unexpired cache entry are sent, batched into
        routeset requests. Results (valid or not) are cached like single
        lookups, so a flight with no known route isn't retried for 4 hours.
        Positions help adsb.im pick the right leg of multi-stop flights.
        """
        wanted: dict[str, tuple[float, float]] = {}
        for callsign, lat, lon in planes:
            normalized = (callsign or "").strip().upper()
            if normalized and self.get_cached_route(normalized) is None:
                wanted[normalized] = (lat or 0.0, lon or 0.0)

        items = list(wanted.items())
        results: dict[str, RouteInfo] = {}
        for i in range(0, len(items), ROUTE_BATCH_SIZE):
            chunk = items[i:i + ROUTE_BATCH_SIZE]
            payload = {
                "planes": [
                    {"callsign": cs, "lat": lat, "lng": lon} for cs, (lat, lon) in chunk
                ]
            }
            data = await self._async_post(payload, f"{len(chunk)} callsigns")
            by_callsign = {}
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and entry.get("callsign"):
                        by_callsign[entry["callsign"].strip().upper()] = entry
            if data is None:
                # Request failed: leave uncached so the next poll retries
                continue
            for cs, _ in chunk:
                results[cs] = _parse_route_entry(cs, by_callsign.get(cs))

        now = dt_util.utcnow()
        self._cache = {
            key: value
            for key, value in self._cache.items()
            if now - value[1] < ROUTE_CACHE_TTL
        }
        for cs, route in results.items():
            self._cache[cs] = (route, now)
        return results

    async def _async_post(self, payload: dict[str, Any], what: str) -> Any:
        """POST to the routeset API; return parsed JSON, or None on failure."""
        try:
            session = async_get_clientsession(self._hass)
            async with asyncio.timeout(ROUTE_API_TIMEOUT):
                async with session.post(
                    ROUTE_API_URL,
                    json=payload,
                    headers={"Accept": "application/json"},
                ) as response:
                    if response.status != 200:
                        _LOGGER.debug(
                            "Route API returned HTTP %d for %s", response.status, what
                        )
                        return None
                    return await response.json()
        except asyncio.TimeoutError:
            _LOGGER.debug("Route API timeout for %s", what)
        except Exception as err:
            _LOGGER.debug("Route API error for %s: %s", what, err)
        return None

    async def _async_fetch_route(self, callsign: str) -> RouteInfo:
        """Fetch one route from the adsb.im API. Never raises."""
        payload = {"planes": [{"callsign": callsign, "lat": 0.0, "lng": 0.0}]}
        data = await self._async_post(payload, callsign)
        if data is None:
            return RouteInfo(callsign=callsign, valid=False)
        return _parse_route_response(callsign, data)


def _parse_route_response(callsign: str, data: Any) -> RouteInfo:
    """Parse adsb.im routeset API response into RouteInfo."""
    try:
        if not isinstance(data, list) or not data:
            return RouteInfo(callsign=callsign, valid=False)

        return _parse_route_entry(callsign, data[0])
    except Exception as err:
        _LOGGER.debug("Failed to parse route response for %s: %s", callsign, err)
        return RouteInfo(callsign=callsign, valid=False)


def _parse_route_entry(callsign: str, entry: Any) -> RouteInfo:
    """Parse one routeset entry (None = not returned) into RouteInfo."""
    try:
        if not isinstance(entry, dict):
            return RouteInfo(callsign=callsign, valid=False)
        airports = entry.get("_airports", [])

        if len(airports) < 2:
            return RouteInfo(callsign=callsign, valid=False)

        stops = [
            {
                "iata": airport.get("iata"),
                "name": airport.get("location") or airport.get("name"),
                "lat": airport.get("lat"),
                "lon": airport.get("lon"),
            }
            for airport in airports
        ]
        return RouteInfo(
            callsign=callsign,
            origin_iata=stops[0]["iata"],
            origin_name=stops[0]["name"],
            destination_iata=stops[-1]["iata"],
            destination_name=stops[-1]["name"],
            valid=True,
            airports=stops,
        )
    except Exception as err:
        _LOGGER.debug("Failed to parse route response for %s: %s", callsign, err)
        return RouteInfo(callsign=callsign, valid=False)
