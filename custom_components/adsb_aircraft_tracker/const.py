"""Constants for ADSB Aircraft Tracker integration."""
from datetime import timedelta

DOMAIN = "adsb_aircraft_tracker"

# Single source of truth for the version, together with manifest.json.
# Home Assistant reads manifest.json; our code (device sw_version, the
# route-lookup User-Agent, the card cache-buster) reads this constant.
# Bump BOTH with scripts/release.sh X.Y.Z — CI fails if they differ.
INTEGRATION_VERSION = "1.11.0"

# tar1090-db (Mictronics) military aircraft database
MILITARY_DB_URL = (
    "https://raw.githubusercontent.com/Mictronics/readsb-protobuf"
    "/dev/webapp/src/db/aircrafts.json"
)
MILITARY_DB_REFRESH_INTERVAL = timedelta(hours=24)

# Entity ids suggested for NEW installs (keyed by sensor_type, which is also
# each entity's translation_key). HA 2026.x otherwise prefixes the device
# name ("ADSB Tracker (<host>)") into generated ids, which broke every README
# example. Existing entities keep whatever id the registry already has; a
# second feeder gets "_2" suffixes. The dashboard card finds entities by
# device + translation_key, so it never depends on these.
SUGGESTED_OBJECT_IDS = {
    "closest_aircraft": "adsb_closest_aircraft",
    "top_aircraft": "adsb_nearest_5_aircraft",
    "all_aircraft": "adsb_all_aircraft",
    "military_details": "adsb_military_aircraft_details",
    "military_database_status": "adsb_military_database_status",
    "military_aircraft": "adsb_military_aircraft_present",
}

# Configuration keys
CONF_ADSB_HOST = "adsb_host"
CONF_ADSB_PORT = "adsb_port"
CONF_ADSB_PATH = "adsb_path"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_DISTANCE_LIMIT = "distance_limit"
CONF_NOTIFICATION_DEVICE = "notification_device"
CONF_EXTERNAL_URL = "external_url"
CONF_MILITARY_NOTIFICATIONS = "military_notifications"
CONF_CLOSE_AIRCRAFT_ENABLED = "close_aircraft_enabled"
CONF_CLOSE_AIRCRAFT_DISTANCE = "close_aircraft_distance"
CONF_CLOSE_AIRCRAFT_ALTITUDE = "close_aircraft_altitude"
CONF_EMERGENCY_NOTIFICATIONS = "emergency_notifications"
# Overhead alert: aircraft inside a cone around straight up. The angle is
# degrees away from straight up; max altitude 0 = no limit.
CONF_OVERHEAD_ENABLED = "overhead_enabled"
CONF_OVERHEAD_ANGLE = "overhead_angle"
CONF_OVERHEAD_MAX_ALTITUDE = "overhead_max_altitude"
# Watched aircraft: the user's own list of tail numbers, ICAO hex codes or
# callsigns, as one comma-separated string. Empty = no watchlist alert.
CONF_WATCHLIST = "watchlist"

# More ways onto the watchlist: ICAO type codes (B52, C17, B74* with a star
# for "anything starting with") and operator names (matched as part of the
# operator the feeder reports). Comma-separated strings like the list itself.
CONF_WATCHLIST_TYPES = "watchlist_types"
CONF_WATCHLIST_OPERATORS = "watchlist_operators"

# Every kind of alert, in the order they are listed in the dialogs
ALERT_KINDS = ("military", "close_aircraft", "overhead", "emergency", "watchlist")
# Plain names for messages about an alert kind ("Low aircraft alerts are off")
ALERT_KIND_NAMES = {
    "military": "Military aircraft",
    "close_aircraft": "Low aircraft",
    "overhead": "Overhead",
    "emergency": "Emergency squawk",
    "watchlist": "Watched aircraft",
}

# Custom alert wording: alert kind -> (title option, message option).
# Empty or unset means the built-in text.
ALERT_TEXT_OPTIONS = {
    kind: (f"{kind}_title", f"{kind}_message") for kind in ALERT_KINDS
}

# Quiet hours: between start and end (local time, may run past midnight) the
# alert kinds listed in CONF_QUIET_ALERTS send no notification. The event
# still fires, so automations keep working.
CONF_QUIET_ENABLED = "quiet_hours_enabled"
CONF_QUIET_START = "quiet_hours_start"
CONF_QUIET_END = "quiet_hours_end"
CONF_QUIET_ALERTS = "quiet_hours_alerts"
DEFAULT_QUIET_ENABLED = False
DEFAULT_QUIET_START = "22:00:00"
DEFAULT_QUIET_END = "07:00:00"
# Emergencies and the user's own watchlist come through unless they say otherwise
DEFAULT_QUIET_ALERTS = ["military", "close_aircraft", "overhead"]
# How long the "Snooze" button on a notification silences that kind of alert;
# 0 = no snooze button
CONF_SNOOZE_MINUTES = "snooze_minutes"
DEFAULT_SNOOZE_MINUTES = 60
MAX_SNOOZE_MINUTES = 1440

# Fired on the Home Assistant event bus for every alert, sent or silenced
EVENT_ALERT = f"{DOMAIN}_alert"
# Contact (email or URL) sent to adsb.im in the User-Agent of route lookups.
# They ask callers for one; empty = the project URL only, never the author's.
CONF_ROUTE_API_CONTACT = "route_api_contact"
# Display units: auto (distance follows Home Assistant, altitude in feet,
# speed in knots), aeronautical, imperial or metric. See units.py.
CONF_UNITS = "units"
DEFAULT_UNITS = "auto"
# Aircraft photos from planespotters.net (nearest aircraft + military)
CONF_AIRCRAFT_PHOTOS = "aircraft_photos"

# Default values
DEFAULT_ADSB_PORT = 8085
DEFAULT_ADSB_PATH = "/data/aircraft.json"

# Paths probed in order when the user leaves the data path blank. Covers
# readsb/tar1090 (bare and under a subpath), FlightAware SkyAware/dump1090-fa,
# and adapters that serve aircraft.json directly or at the root.
ADSB_PATH_CANDIDATES = (
    DEFAULT_ADSB_PATH,
    "/tar1090/data/aircraft.json",
    "/skyaware/data/aircraft.json",
    "/dump1090-fa/data/aircraft.json",
    "/dump1090/data/aircraft.json",
    "/aircraft.json",
    "/",
)
DEFAULT_UPDATE_INTERVAL = 10
DEFAULT_DISTANCE_LIMIT = 0
DEFAULT_MILITARY_NOTIFICATIONS = True
DEFAULT_CLOSE_AIRCRAFT_ENABLED = True
DEFAULT_CLOSE_AIRCRAFT_DISTANCE = 2.0
DEFAULT_CLOSE_AIRCRAFT_ALTITUDE = 3000
DEFAULT_EMERGENCY_NOTIFICATIONS = True
DEFAULT_OVERHEAD_ENABLED = False
DEFAULT_OVERHEAD_ANGLE = 15
DEFAULT_OVERHEAD_MAX_ALTITUDE = 0
# Diagram of the overhead cone, served for the notification options dialog
OVERHEAD_DIAGRAM_URL = f"/{DOMAIN}/overhead-cone.svg"
DEFAULT_AIRCRAFT_PHOTOS = True

# ICAO 3-letter airline codes to spoken names for TTS
AIRLINE_CODE_MAP = {
    "AAL": "American",
    "AAY": "Allegiant",
    "ACA": "Air Canada",
    "AFR": "Air France",
    "AIC": "Air India",
    "AMX": "Aeromexico",
    "ASA": "Alaska",
    "BAW": "British Airways",
    "CPA": "Cathay Pacific",
    "DAL": "Delta",
    "DLH": "Lufthansa",
    "EDV": "Endeavor",
    "ENY": "Envoy",
    "FDX": "FedEx",
    "FFT": "Frontier",
    "GJS": "GoJet",
    "HAL": "Hawaiian",
    "JBU": "JetBlue",
    "JIA": "PSA Airlines",
    "KAL": "Korean Air",
    "NKS": "Spirit",
    "PDT": "Piedmont",
    "QFA": "Qantas",
    "RPA": "Republic",
    "SKW": "SkyWest",
    "SWA": "Southwest",
    "THY": "Turkish",
    "UAL": "United",
    "UPS": "UPS",
    "VOI": "Volaris",
    "WJA": "WestJet",
}

# Aviation abbreviations to keep uppercase during title-casing
AVIATION_ABBREVIATIONS = {
    "ERJ", "CRJ", "ATR", "EMB", "MD", "DC", "DHC",
    "BAE", "RJ", "SF", "PC", "TBM", "SR",
    "E75", "E70", "E90", "E45",
    "II", "III", "IV", "MAX", "ER", "LR",
}

# Maps spoken aircraft type words to filter criteria
# "engine_type" values come from the ICAO types database field
# "category_prefix" matches the first char of the ICAO aircraft_type code
AIRCRAFT_TYPE_KEYWORDS = {
    "helicopter": {
        "terms": ["helicopter", "helicopters", "chopper", "choppers", "heli", "helis", "rotorcraft"],
        "category_prefix": "H",
        "description_keywords": ["HELICOPTER"],
    },
    "jet": {
        "terms": ["jet", "jets", "airliner", "airliners"],
        "engine_type": "Jet",
        "description_keywords": [],
    },
    "turboprop": {
        "terms": ["turboprop", "turboprops", "prop", "props", "propeller"],
        "engine_type": "Turboprop",
        "description_keywords": [],
    },
    "piston": {
        "terms": ["piston", "cessna", "small plane", "small planes", "light aircraft"],
        "engine_type": "Piston",
        "description_keywords": ["CESSNA", "PIPER", "BEECH", "CIRRUS", "MOONEY"],
    },
}
