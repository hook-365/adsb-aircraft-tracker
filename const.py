"""Constants for ADSB Aircraft Tracker integration."""

DOMAIN = "adsb_aircraft_tracker"

# Configuration keys
CONF_ADSB_HOST = "adsb_host"
CONF_ADSB_PORT = "adsb_port"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_DISTANCE_LIMIT = "distance_limit"
CONF_NOTIFICATION_DEVICE = "notification_device"
CONF_EXTERNAL_URL = "external_url"
CONF_MILITARY_NOTIFICATIONS = "military_notifications"
CONF_CLOSE_AIRCRAFT_ENABLED = "close_aircraft_enabled"
CONF_CLOSE_AIRCRAFT_DISTANCE = "close_aircraft_distance"
CONF_CLOSE_AIRCRAFT_ALTITUDE = "close_aircraft_altitude"
CONF_EMERGENCY_NOTIFICATIONS = "emergency_notifications"

# Default values
DEFAULT_ADSB_PORT = 8085
DEFAULT_UPDATE_INTERVAL = 10
DEFAULT_DISTANCE_LIMIT = 0
DEFAULT_MILITARY_NOTIFICATIONS = True
DEFAULT_CLOSE_AIRCRAFT_ENABLED = True
DEFAULT_CLOSE_AIRCRAFT_DISTANCE = 2.0
DEFAULT_CLOSE_AIRCRAFT_ALTITUDE = 3000
DEFAULT_EMERGENCY_NOTIFICATIONS = True

