"""Data update coordinator for ADSB Aircraft Tracker."""
from __future__ import annotations

import asyncio
import bisect
import json
import logging
import os
from array import array
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .geo import distance_and_bearing
from .const import (
    DOMAIN,
    CONF_ADSB_HOST,
    CONF_ADSB_PORT,
    CONF_ADSB_PATH,
    CONF_DISTANCE_LIMIT,
    DEFAULT_ADSB_PORT,
    DEFAULT_ADSB_PATH,
    DEFAULT_DISTANCE_LIMIT,
    MILITARY_DB_URL,
)

_LOGGER = logging.getLogger(__name__)

# readsb's r_dst is in nautical miles
NM_TO_MI = 1.15078


class AircraftRegistry:
    """Compact ICAO hex -> (registration, type code) lookup.

    Fills in tail/type for feeders that don't send them (dump1090-fa/PiAware
    and most bridges; readsb/tar1090 already include "r"/"t"). The Mictronics
    DB has ~450k entries; a plain dict of them costs ~60 MB, so they're packed
    into two int arrays plus one byte blob (~8 MB) and found by binary search.
    """

    def __init__(self, entries: dict[str, list[str]]) -> None:
        rows = []
        for icao_hex, info in entries.items():
            if len(info) < 2 or not (info[0] or info[1]):
                continue
            try:
                key = int(icao_hex, 16)
            except ValueError:
                continue
            rows.append((key, f"{info[0]}\t{info[1]}".encode()))
        rows.sort()
        self._keys = array("I", (key for key, _ in rows))
        self._offsets = array("I", [0])
        chunks = []
        for _, value in rows:
            chunks.append(value)
            self._offsets.append(self._offsets[-1] + len(value))
        self._blob = b"".join(chunks)

    def __len__(self) -> int:
        return len(self._keys)

    def lookup(self, icao_hex: str | None) -> tuple[str | None, str | None]:
        """Return (registration, type code) for a hex code, or (None, None)."""
        try:
            key = int(icao_hex or "", 16)
        except ValueError:  # "~"-prefixed non-ICAO addresses, blanks
            return None, None
        i = bisect.bisect_left(self._keys, key)
        if i == len(self._keys) or self._keys[i] != key:
            return None, None
        reg, _, type_code = (
            self._blob[self._offsets[i]:self._offsets[i + 1]].decode().partition("\t")
        )
        return reg or None, type_code or None


class ADSBDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching ADSB aircraft data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize coordinator."""
        self.config_entry = config_entry
        # Options (UI-editable) override the original setup data
        config = {**config_entry.data, **config_entry.options}
        self.adsb_host = config[CONF_ADSB_HOST]
        self.adsb_port = config.get(CONF_ADSB_PORT, DEFAULT_ADSB_PORT)
        self.distance_limit = config.get(CONF_DISTANCE_LIMIT, DEFAULT_DISTANCE_LIMIT)

        # Build ADSB URL (path is discovered by the config flow; entries
        # created before path discovery existed use the tar1090 default)
        adsb_path = config.get(CONF_ADSB_PATH) or DEFAULT_ADSB_PATH
        self.adsb_url = f"http://{self.adsb_host}:{self.adsb_port}{adsb_path}"

        # Load aircraft types database (will be loaded async after init)
        self.aircraft_types_db = {}

        # Military aircraft database (tar1090-db / Mictronics), owned by the
        # coordinator — all consumers (sensors, notify, intents) share it.
        self._military_database: dict[str, dict[str, str]] | None = None
        self._db_last_updated: datetime | None = None
        self._db_loading = False
        # Registration/type for every aircraft in the same download
        self._registry: AircraftRegistry | None = None

        # Set by __init__ after setup; routes fill the route_* attributes
        self.route_client = None
        self._route_lookup_running = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        
        # Schedule async loading of aircraft types database
        self.hass.async_create_task(self._async_load_aircraft_types_db())

        # Initial military database load (refreshed daily by a timer in __init__)
        self.hass.async_create_task(self._async_load_military_database())

    async def _async_load_aircraft_types_db(self) -> None:
        """Load aircraft types database from tar1090-db asynchronously."""
        try:
            import aiofiles
            db_path = os.path.join(os.path.dirname(__file__), "icao_aircraft_types.json")
            if os.path.exists(db_path):
                async with aiofiles.open(db_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    self.aircraft_types_db = json.loads(content)
                    _LOGGER.info("Loaded %d aircraft types from tar1090-db", len(self.aircraft_types_db))
            else:
                _LOGGER.warning("Aircraft types database not found at %s", db_path)
                self.aircraft_types_db = {}
        except ImportError:
            # Fallback to sync loading if aiofiles not available
            try:
                db_path = os.path.join(os.path.dirname(__file__), "icao_aircraft_types.json")
                if os.path.exists(db_path):
                    with open(db_path, "r", encoding="utf-8") as f:
                        self.aircraft_types_db = json.load(f)
                        _LOGGER.info("Loaded %d aircraft types from tar1090-db (sync fallback)", len(self.aircraft_types_db))
                else:
                    _LOGGER.warning("Aircraft types database not found at %s", db_path)
                    self.aircraft_types_db = {}
            except Exception as err:
                _LOGGER.error("Failed to load aircraft types database (sync fallback): %s", err)
                self.aircraft_types_db = {}
        except Exception as err:
            _LOGGER.error("Failed to load aircraft types database: %s", err)
            self.aircraft_types_db = {}

    def get_aircraft_type_info(self, aircraft_type: str | None) -> dict[str, Any]:
        """Get detailed aircraft type information from tar1090-db."""
        if not aircraft_type or not self.aircraft_types_db:
            return {"description": "Unknown aircraft", "category": "Unknown", "weight_class": "Unknown"}
        
        # Look up in aircraft types database
        type_info = self.aircraft_types_db.get(aircraft_type.upper(), {})
        
        # Parse description field (format: engine_count + engine_type + aircraft_category)
        desc = type_info.get("desc", "")
        wtc = type_info.get("wtc", "L")  # Weight category: L=Light, M=Medium, H=Heavy
        
        # Parse engine info from description
        engine_count = "Unknown"
        engine_type = "Unknown"
        category = "Unknown"
        
        if desc:
            # First character is usually engine count (1-8) or special codes
            if desc[0].isdigit():
                engine_count = desc[0]
            elif desc[0] in "ABCGHILRS":
                # Special engine configurations
                engine_count = {"A": "Amphibian", "B": "Balloon", "G": "Gyrocopter", 
                              "H": "Helicopter", "L": "Glider", "R": "Rotorcraft", 
                              "S": "Seaplane"}.get(desc[0], "Special")
            
            # Second character is engine type
            if len(desc) > 1:
                engine_type = {"P": "Piston", "T": "Turboprop", "J": "Jet", 
                             "E": "Electric", "R": "Rocket"}.get(desc[1], "Unknown")
            
            # Third character is aircraft category
            if len(desc) > 2:
                category = {"P": "Landplane", "S": "Seaplane", "A": "Amphibian",
                          "H": "Helicopter", "G": "Gyrocopter", "T": "Tiltrotor"}.get(desc[2], "Aircraft")
        
        # Create friendly description
        if aircraft_type.upper() in self.aircraft_types_db:
            friendly_desc = self._create_friendly_description(aircraft_type.upper(), engine_count, engine_type, category)
        else:
            friendly_desc = f"{aircraft_type} ({category})" if category != "Unknown" else aircraft_type
        
        return {
            "description": friendly_desc,
            "category": category,
            "weight_class": {"L": "Light", "M": "Medium", "H": "Heavy"}.get(wtc, "Unknown"),
            "engine_count": engine_count,
            "engine_type": engine_type,
            "raw_desc": desc,
            "raw_wtc": wtc
        }

    def _create_friendly_description(self, aircraft_type: str, engine_count: str, engine_type: str, category: str) -> str:
        """Create a friendly description for known aircraft types."""
        # Known aircraft mappings for better descriptions
        aircraft_names = {
            "A320": "Airbus A320",
            "A321": "Airbus A321",
            "A330": "Airbus A330",
            "A340": "Airbus A340",
            "A350": "Airbus A350",
            "A380": "Airbus A380",
            "B737": "Boeing 737",
            "B738": "Boeing 737-800",
            "B739": "Boeing 737-900",
            "B744": "Boeing 747-400",
            "B748": "Boeing 747-8",
            "B752": "Boeing 757-200",
            "B763": "Boeing 767-300",
            "B772": "Boeing 777-200",
            "B773": "Boeing 777-300",
            "B77W": "Boeing 777-300ER",
            "B788": "Boeing 787-8",
            "B789": "Boeing 787-9",
            "C130": "Lockheed C-130 Hercules",
            "C135": "Boeing C-135",
            "C17": "Boeing C-17 Globemaster III",
            "KC135": "Boeing KC-135 Stratotanker",
            "KC10": "McDonnell Douglas KC-10 Extender",
            "KC46": "Boeing KC-46 Pegasus",
            "F16": "General Dynamics F-16 Fighting Falcon",
            "F15": "McDonnell Douglas F-15 Eagle",
            "F18": "McDonnell Douglas F/A-18 Hornet",
            "F22": "Lockheed Martin F-22 Raptor",
            "F35": "Lockheed Martin F-35 Lightning II",
            "C172": "Cessna 172 Skyhawk",
            "C182": "Cessna 182 Skylane",
            "C206": "Cessna 206 Stationair",
            "PA28": "Piper PA-28 Cherokee",
            "P28A": "Piper PA-28 Cherokee",
            "BE20": "Beechcraft King Air",
            "BE35": "Beechcraft Bonanza",
            "UH60": "Sikorsky UH-60 Black Hawk",
            "CH47": "Boeing CH-47 Chinook",
            "AH64": "Boeing AH-64 Apache"
        }
        
        friendly_name = aircraft_names.get(aircraft_type, aircraft_type)
        
        # Add engine information if available and not helicopter
        if category != "Helicopter" and engine_count.isdigit() and engine_type != "Unknown":
            if int(engine_count) > 1:
                engine_desc = f"{engine_count}-engine {engine_type.lower()}"
            else:
                engine_desc = f"Single-engine {engine_type.lower()}"
            return f"{friendly_name} ({engine_desc})"
        
        return friendly_name

    def get_distance_unit(self) -> str:
        """Get the appropriate distance unit based on Home Assistant unit system."""
        return "km" if self.hass.config.units.length == "km" else "mi"
    
    def convert_distance(self, miles: float) -> float:
        """Convert miles to appropriate unit based on Home Assistant unit system."""
        if self.hass.config.units.length == "km":
            return miles * 1.60934  # Convert to kilometers
        return miles
    
    def format_distance(self, miles: float | None) -> str:
        """Format distance with appropriate unit."""
        if miles is None or miles == 0:
            return "Unknown"
        if self.hass.config.units.length == "km":
            km = miles * 1.60934
            return f"{km:.1f} km"
        return f"{miles:.1f} mi"

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch aircraft data from ADSB source."""
        try:
            session = async_get_clientsession(self.hass)

            async with asyncio.timeout(10):
                async with session.get(self.adsb_url) as response:
                    if response.status != 200:
                        raise UpdateFailed(
                            f"Error fetching ADSB data: HTTP {response.status}"
                        )
                    # content_type=None: adapters often serve JSON as text/plain
                    data = await response.json(content_type=None)

        except UpdateFailed:
            raise
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching ADSB data from {self.adsb_url}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching ADSB data: {err}") from err
        except (json.JSONDecodeError, ValueError) as err:
            raise UpdateFailed(f"Invalid JSON from ADSB source: {err}") from err

        # Validate data structure
        if "aircraft" not in data:
            raise UpdateFailed("Invalid ADSB data: missing aircraft array")

        # Process and enrich aircraft data. Include all aircraft, even without
        # position data (important for military detection).
        processed_aircraft = [self._process_aircraft(plane) for plane in data["aircraft"]]

        # Filter by distance if a limit is set (limit and distance_mi are
        # both statute miles; aircraft with no known distance are dropped)
        if self.distance_limit > 0:
            processed_aircraft = [
                plane for plane in processed_aircraft
                if plane["distance_mi"] is not None and plane["distance_mi"] <= self.distance_limit
            ]

        # Sort by distance (closest first), putting aircraft without distance at end
        processed_aircraft.sort(key=lambda x: x.get("distance_mi") if x.get("distance_mi") is not None else 999)

        self._attach_routes(processed_aircraft)

        result = {
            "aircraft": processed_aircraft,
            "aircraft_count": len(processed_aircraft),
            "last_update": data.get("now"),
            "total_messages": data.get("messages", 0),
        }

        # Check for notifications against the fresh data
        if getattr(self, "notification_manager", None):
            try:
                await self.notification_manager.check_and_notify(processed_aircraft)
            except Exception as err:
                _LOGGER.error("Error checking notifications: %s", err)

        return result

    def _attach_routes(
        self, aircraft_list: list[dict[str, Any]], lookup: bool = True
    ) -> None:
        """Add cached routes to aircraft, and look up any new callsigns.

        Every aircraft with a callsign gets a route lookup the first time it's
        seen. New callsigns go out together in one background batch request
        (one batch at a time), and results, including "no route known", are
        cached for 4 hours, so adsb.im sees roughly one small request per
        poll that has newly arrived flights.
        """
        if self.route_client is None:
            return
        uncached = []
        for aircraft in aircraft_list:
            callsign = aircraft.get("flight")
            if not callsign:
                continue
            route = self.route_client.get_cached_route(callsign)
            if route is None:
                uncached.append(
                    (callsign, aircraft.get("latitude"), aircraft.get("longitude"))
                )
            elif route.valid:
                route = route.for_position(
                    aircraft.get("latitude"), aircraft.get("longitude"), aircraft.get("heading")
                )
                aircraft["route_origin"] = route.origin_iata
                aircraft["route_origin_name"] = route.origin_name
                aircraft["route_destination"] = route.destination_iata
                aircraft["route_destination_name"] = route.destination_name

        if lookup and uncached and not self._route_lookup_running:
            self._route_lookup_running = True
            self.hass.async_create_background_task(
                self._async_lookup_routes(uncached), f"{DOMAIN} route lookup"
            )

    async def _async_lookup_routes(
        self, planes: list[tuple[str, float | None, float | None]]
    ) -> None:
        """Fetch routes in the background, then refresh entities with them."""
        try:
            routes = await self.route_client.async_get_routes(planes)
        finally:
            self._route_lookup_running = False
        if any(route.valid for route in routes.values()) and self.data:
            # Apply to the current data right away instead of waiting for
            # the next poll (failed callsigns wait for that poll to retry)
            self._attach_routes(self.data["aircraft"], lookup=False)
            self.async_update_listeners()

    def _process_aircraft(self, plane: dict[str, Any]) -> dict[str, Any]:
        """Process and enrich individual aircraft data."""
        # readsb/tar1090 send registration ("r") and type ("t"); other
        # feeders don't, so fill them from the downloaded aircraft DB
        tail = plane.get("r")
        aircraft_type = plane.get("t")
        if (not tail or not aircraft_type) and self._registry is not None:
            db_tail, db_type = self._registry.lookup(plane.get("hex"))
            tail = tail or db_tail
            aircraft_type = aircraft_type or db_type

        # Get enhanced aircraft type information
        type_info = self.get_aircraft_type_info(aircraft_type)

        # readsb reports alt_baro as the string "ground" for taxiing aircraft —
        # normalize so every consumer can rely on altitude_ft being numeric
        # (0 = on ground or unknown; the on_ground flag disambiguates).
        alt_baro = plane.get("alt_baro")
        on_ground = alt_baro == "ground"
        altitude_ft = alt_baro if isinstance(alt_baro, (int, float)) else 0
        gs = plane.get("gs")
        speed_kts = round(gs, 0) if isinstance(gs, (int, float)) else 0
        # Distance/bearing from HA's home location. Computed here rather than
        # taken from readsb's r_dst/r_dir: those are nautical miles, relative
        # to the receiver, and absent entirely on dump1090-fa (PiAware) and
        # most bridges. r_dst is only a fallback when there's no position.
        lat, lon = plane.get("lat"), plane.get("lon")
        distance_mi = None
        direction = None
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            distance_mi, direction = distance_and_bearing(
                self.hass.config.latitude, self.hass.config.longitude, lat, lon
            )
            distance_mi = round(distance_mi, 1)
            direction = round(direction, 1)
        elif isinstance(plane.get("r_dst"), (int, float)):
            distance_mi = round(plane["r_dst"] * NM_TO_MI, 1)
            direction = plane.get("r_dir")

        baro_rate = plane.get("baro_rate")
        vertical_rate_fpm = baro_rate if isinstance(baro_rate, (int, float)) else 0
        
        # Use enhanced description if available, fallback to original
        enhanced_description = type_info.get("description", "Unknown aircraft")
        if enhanced_description == "Unknown aircraft" or enhanced_description == aircraft_type:
            # Fallback to original description if no enhancement
            enhanced_description = plane.get("desc", "Unknown aircraft")
        
        return {
            # Basic identifiers
            "hex": plane.get("hex"),
            "tail": tail or "Unknown",
            "flight": (plane.get("flight") or "").strip() or None,
            
            # Aircraft details (enhanced with tar1090-db)
            "aircraft_type": aircraft_type,
            "description": enhanced_description,
            "category": type_info.get("category", "Unknown"),
            "weight_class": type_info.get("weight_class", "Unknown"),
            "engine_count": type_info.get("engine_count", "Unknown"),
            "engine_type": type_info.get("engine_type", "Unknown"),
            "operator": plane.get("ownOp"),
            "year": plane.get("year"),
            
            # Position and movement
            "latitude": plane.get("lat"),
            "longitude": plane.get("lon"),
            "distance_mi": distance_mi,
            "direction": direction,
            
            # Flight data
            "altitude_ft": altitude_ft,
            "on_ground": on_ground,
            "altitude_geom": plane.get("alt_geom"),
            "speed_kts": speed_kts,
            "heading": plane.get("track"),
            "vertical_rate_fpm": vertical_rate_fpm,
            
            # Navigation
            "squawk": plane.get("squawk"),
            "emergency": plane.get("emergency", "none"),
            "nav_altitude": plane.get("nav_altitude_mcp"),
            "nav_heading": plane.get("nav_heading"),
            "nav_qnh": plane.get("nav_qnh"),
            "nac_p": plane.get("nac_p"),
            "adsb_version": plane.get("version"),

            # Technical
            "icao_category": plane.get("category"),  # Original ICAO category
            "messages": plane.get("messages", 0),
            "seen": plane.get("seen", 0),
            "rssi": plane.get("rssi"),
            
            # Raw tar1090-db info for debugging
            "raw_type_desc": type_info.get("raw_desc", ""),
            "raw_weight_class": type_info.get("raw_wtc", "L"),
        }
    
    async def _async_load_military_database(self) -> None:
        """Download and parse the military aircraft database.

        Safe to call repeatedly (concurrent calls are dropped). Called at
        startup, by the daily refresh timer, and by the manual reload service.
        """
        if self._db_loading:
            _LOGGER.debug("Military database load already in progress, skipping")
            return
        self._db_loading = True
        try:
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(60):
                async with session.get(MILITARY_DB_URL) as response:
                    if response.status != 200:
                        _LOGGER.warning(
                            "Failed to load military database: HTTP %d", response.status
                        )
                        return
                    content = await response.text()

            # ~700k entries — parse and filter off the event loop
            military_db, registry = await self.hass.async_add_executor_job(
                _parse_aircraft_db, content
            )
            self._military_database = military_db
            self._registry = registry
            self._db_last_updated = datetime.now()
            _LOGGER.info(
                "Loaded %d military aircraft and %d registrations from tar1090-db",
                len(military_db), len(registry),
            )
        except Exception as err:
            _LOGGER.error("Error loading military database: %s", err)
        finally:
            self._db_loading = False

    def detect_military_aircraft(
        self, aircraft_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return the subset of aircraft found in the military database.

        Database-only detection — no pattern-matching fallback. Returns an
        empty list until the database has loaded.
        """
        if not self._military_database:
            return []
        military = []
        for aircraft in aircraft_list:
            hex_code = (aircraft.get("hex") or "").upper()
            db_info = self._military_database.get(hex_code)
            if db_info:
                aircraft["_db_info"] = db_info
                aircraft["_detection_reasons"] = ["DATABASE_MATCH"]
                military.append(aircraft)
        return military

    def get_military_database_status(self) -> dict[str, Any]:
        """Get military database status for monitoring."""
        return {
            "database_loaded": self._military_database is not None,
            "database_size": len(self._military_database) if self._military_database else 0,
            "last_updated": self._db_last_updated.isoformat() if self._db_last_updated else None,
            "last_updated_friendly": self._db_last_updated.strftime("%Y-%m-%d %H:%M:%S") if self._db_last_updated else "Never",
        }


def _parse_aircraft_db(
    content: str,
) -> tuple[dict[str, dict[str, str]], AircraftRegistry]:
    """Parse the Mictronics aircraft DB into the military subset (flag "10")
    and a compact registration/type registry for all aircraft."""
    db_data = json.loads(content)
    military_db = {}
    for icao_hex, aircraft_info in db_data.items():
        if len(aircraft_info) >= 3 and aircraft_info[2] == "10":
            military_db[icao_hex.upper()] = {
                "tail": aircraft_info[0],
                "type": aircraft_info[1],
                "flag": aircraft_info[2],
                "description": aircraft_info[3] if len(aircraft_info) > 3 else "",
            }
    return military_db, AircraftRegistry(db_data)