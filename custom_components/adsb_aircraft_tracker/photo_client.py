"""Aircraft photo lookup (planespotters.net) for ADSB Aircraft Tracker."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .route_client import build_user_agent

_LOGGER = logging.getLogger(__name__)

# Public, keyless API: one request per ICAO hex, answers with up to one
# photo (thumbnail + larger thumbnail + photo page + photographer).
# Their terms: credit the photographer and link back to the photo page,
# which the cards and attributes do. https://www.planespotters.net/photo/api
PHOTO_API_URL = "https://api.planespotters.net/pub/photos/hex/{hex}"
PHOTO_API_TIMEOUT = 5
# Photos for an airframe rarely change; "no photo" is also worth remembering
# (most GA aircraft have none) so the same hex isn't asked about every poll.
PHOTO_CACHE_TTL = timedelta(hours=24)
# After a refusal (403/429) or upstream error (5xx), stop asking for a while.
PHOTO_API_BACKOFF = timedelta(minutes=10)
# Parallel requests per lookup batch; lookups are only ever for the handful
# of aircraft the cards show, so this stays polite.
PHOTO_CONCURRENCY = 2


@dataclass(frozen=True)
class PhotoInfo:
    """One photo of an airframe. `valid` False = looked up, none known."""

    hex: str
    thumbnail: str | None = None  # ~200 px wide
    large: str | None = None  # ~420 px wide
    link: str | None = None  # photo page on planespotters.net (attribution)
    photographer: str | None = None
    valid: bool = False


class PhotoClient:
    """Async client for aircraft photos with a per-hex TTL cache."""

    def __init__(self, hass: HomeAssistant, version: str = "0", contact: str = "") -> None:
        """Initialize. `version` and `contact` go into the User-Agent."""
        self._hass = hass
        self._cache: dict[str, tuple[PhotoInfo, datetime]] = {}
        self._blocked_until: datetime | None = None
        self._user_agent = build_user_agent(version, contact)

    def is_backing_off(self) -> bool:
        """True while a recent refusal/error has paused photo lookups."""
        return self._blocked_until is not None and dt_util.utcnow() < self._blocked_until

    def get_cached(self, hex_code: str | None) -> PhotoInfo | None:
        """Cached photo for a hex, or None if never looked up (or expired)."""
        key = _normalize(hex_code)
        if not key:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        photo, fetched = entry
        if dt_util.utcnow() - fetched >= PHOTO_CACHE_TTL:
            del self._cache[key]
            return None
        return photo

    async def async_get_photos(self, hexes: list[str]) -> dict[str, PhotoInfo]:
        """Look up photos for the given hexes (uncached ones only). Never raises."""
        wanted = []
        for hex_code in hexes:
            key = _normalize(hex_code)
            if key and key not in wanted and self.get_cached(key) is None:
                wanted.append(key)
        if not wanted or self.is_backing_off():
            return {}

        semaphore = asyncio.Semaphore(PHOTO_CONCURRENCY)

        async def one(key: str) -> tuple[str, PhotoInfo | None]:
            async with semaphore:
                return key, await self._async_fetch(key)

        results: dict[str, PhotoInfo] = {}
        now = dt_util.utcnow()
        for key, photo in await asyncio.gather(*(one(k) for k in wanted)):
            if photo is None:
                continue  # request failed: leave uncached so a later poll retries
            results[key] = photo
            self._cache[key] = (photo, now)
        # Drop expired entries so the cache can't grow without bound
        self._cache = {
            k: v for k, v in self._cache.items() if now - v[1] < PHOTO_CACHE_TTL
        }
        return results

    async def _async_fetch(self, key: str) -> PhotoInfo | None:
        """GET one hex; PhotoInfo (valid or not) on an answer, None on failure."""
        if self.is_backing_off():
            return None
        try:
            session = async_get_clientsession(self._hass)
            async with asyncio.timeout(PHOTO_API_TIMEOUT):
                async with session.get(
                    PHOTO_API_URL.format(hex=key),
                    headers={"Accept": "application/json", "User-Agent": self._user_agent},
                ) as response:
                    if response.status == 200:
                        self._blocked_until = None
                        return _parse_photo_response(key, await response.json())
                    if response.status == 404:
                        return PhotoInfo(hex=key, valid=False)
                    if response.status in (403, 429) or response.status >= 500:
                        self._blocked_until = dt_util.utcnow() + PHOTO_API_BACKOFF
                        _LOGGER.warning(
                            "Photo API (planespotters.net) returned HTTP %d for %s; "
                            "pausing photo lookups for %s",
                            response.status, key, PHOTO_API_BACKOFF,
                        )
                    else:
                        _LOGGER.debug("Photo API returned HTTP %d for %s", response.status, key)
        except asyncio.TimeoutError:
            _LOGGER.debug("Photo API timeout for %s", key)
        except Exception as err:  # noqa: BLE001 - never let a lookup break polling
            _LOGGER.debug("Photo API error for %s: %s", key, err)
        return None


def _normalize(hex_code: str | None) -> str | None:
    """Lowercase 6-char ICAO hex, or None (TIS-B/MLAT '~' hexes have no photos)."""
    if not isinstance(hex_code, str):
        return None
    key = hex_code.strip().lower()
    return key if len(key) == 6 and key.isalnum() else None


def _parse_photo_response(key: str, data: Any) -> PhotoInfo:
    """Parse a planespotters.net `pub/photos/hex` response into PhotoInfo."""
    try:
        photos = data.get("photos") if isinstance(data, dict) else None
        if not photos or not isinstance(photos[0], dict):
            return PhotoInfo(hex=key, valid=False)
        photo = photos[0]
        thumbnail = (photo.get("thumbnail") or {}).get("src")
        large = (photo.get("thumbnail_large") or {}).get("src") or thumbnail
        if not thumbnail:
            return PhotoInfo(hex=key, valid=False)
        return PhotoInfo(
            hex=key,
            thumbnail=thumbnail,
            large=large,
            link=photo.get("link"),
            photographer=photo.get("photographer"),
            valid=True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed to parse photo response for %s: %s", key, err)
        return PhotoInfo(hex=key, valid=False)
