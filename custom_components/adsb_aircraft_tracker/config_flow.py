"""Config flow for ADSB Aircraft Tracker integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_ADSB_HOST,
    CONF_ADSB_PORT,
    CONF_ADSB_PATH,
    CONF_UPDATE_INTERVAL,
    CONF_DISTANCE_LIMIT,
    CONF_NOTIFICATION_DEVICE,
    CONF_EXTERNAL_URL,
    CONF_MILITARY_NOTIFICATIONS,
    CONF_CLOSE_AIRCRAFT_ENABLED,
    CONF_CLOSE_AIRCRAFT_DISTANCE,
    CONF_CLOSE_AIRCRAFT_ALTITUDE,
    CONF_EMERGENCY_NOTIFICATIONS,
    CONF_OVERHEAD_ENABLED,
    CONF_OVERHEAD_ANGLE,
    CONF_OVERHEAD_MAX_ALTITUDE,
    ALERT_TEXT_OPTIONS,
    CONF_ROUTE_API_CONTACT,
    CONF_AIRCRAFT_PHOTOS,
    CONF_UNITS,
    DEFAULT_UNITS,
    DEFAULT_AIRCRAFT_PHOTOS,
    DEFAULT_ADSB_PORT,
    ADSB_PATH_CANDIDATES,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_DISTANCE_LIMIT,
    DEFAULT_MILITARY_NOTIFICATIONS,
    DEFAULT_CLOSE_AIRCRAFT_ENABLED,
    DEFAULT_CLOSE_AIRCRAFT_DISTANCE,
    DEFAULT_CLOSE_AIRCRAFT_ALTITUDE,
    DEFAULT_EMERGENCY_NOTIFICATIONS,
    DEFAULT_OVERHEAD_ENABLED,
    DEFAULT_OVERHEAD_ANGLE,
    DEFAULT_OVERHEAD_MAX_ALTITUDE,
    INTEGRATION_VERSION,
    OVERHEAD_DIAGRAM_URL,
)

from . import alert_text
from .geo import cone_footprint_mi, cone_sky_share
from .units import UNIT_PRESETS, UnitSystem, resolve as resolve_units

_LOGGER = logging.getLogger(__name__)

# Limits of the threshold fields, in the stored units (miles and feet)
MAX_DISTANCE_LIMIT_MI = 1000
MAX_CLOSE_DISTANCE_MI = 50
MIN_CLOSE_ALTITUDE_FT = 100
MAX_CLOSE_ALTITUDE_FT = 10000
MAX_OVERHEAD_ALTITUDE_FT = 60000


def _setup_units(hass: HomeAssistant | None) -> UnitSystem:
    """Units during first setup: no Units option yet, so follow Home Assistant."""
    return resolve_units(DEFAULT_UNITS, bool(hass and hass.config.units.length == "km"))


def _edited(submitted: float, shown: float, stored: float, convert) -> float:
    """Value to store for a threshold field shown in display units.

    A field left as it was shown keeps the stored value exactly, so opening
    and saving the dialog never shifts a threshold by a rounding step.
    """
    return stored if submitted == shown else convert(submitted)


def get_user_data_schema(hass=None):
    """Get the user data schema with helpful defaults and labels."""
    max_distance = _setup_units(hass).distance_to_display(MAX_DISTANCE_LIMIT_MI, 0)

    return vol.Schema(
        {
            vol.Required(CONF_ADSB_HOST): str,
            vol.Optional(CONF_ADSB_PORT, default=DEFAULT_ADSB_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(CONF_ADSB_PATH, default=""): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            vol.Optional(CONF_DISTANCE_LIMIT, default=DEFAULT_DISTANCE_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=0, max=max_distance)),
        }
    )


def _normalize_path(path: str) -> str:
    """Return a data path with exactly one leading slash ("" stays "")."""
    path = path.strip()
    if not path:
        return ""
    return "/" + path.lstrip("/")


async def _probe_path(
    session: aiohttp.ClientSession, host: str, port: int, path: str
) -> dict[str, Any]:
    """Fetch one candidate URL and return its parsed aircraft JSON.

    Raises InvalidHost for a non-200 response and InvalidADSBData for a 200
    that isn't aircraft JSON; connection-level errors propagate unchanged.
    """
    url = f"http://{host}:{port}{path}"
    async with asyncio.timeout(10):
        async with session.get(url) as response:
            if response.status != 200:
                raise InvalidHost(f"HTTP {response.status} from {url}")
            # content_type=None: adapters often serve JSON as text/plain
            try:
                json_data = await response.json(content_type=None)
            except ValueError as err:
                raise InvalidADSBData(f"Non-JSON response from {url}") from err

    if not isinstance(json_data, dict) or not isinstance(json_data.get("aircraft"), list):
        raise InvalidADSBData(f"No aircraft list in response from {url}")
    return json_data


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    With an explicit data path only that path is tried; left blank, the
    known feeder paths (ADSB_PATH_CANDIDATES) are probed in order and the
    first one serving aircraft JSON wins.
    """

    host = data[CONF_ADSB_HOST].strip()
    port = data[CONF_ADSB_PORT]
    explicit_path = _normalize_path(data.get(CONF_ADSB_PATH, ""))
    candidates = (explicit_path,) if explicit_path else ADSB_PATH_CANDIDATES

    session = async_get_clientsession(hass)
    last_error: InvalidHost | InvalidADSBData | None = None

    try:
        for path in candidates:
            try:
                json_data = await _probe_path(session, host, port, path)
            except (InvalidHost, InvalidADSBData) as err:
                _LOGGER.debug("ADSB probe failed: %s", err)
                # Prefer reporting "reached a server but bad data" over a 404
                if last_error is None or isinstance(err, InvalidADSBData):
                    last_error = err
                continue

            return {
                "title": f"ADSB Tracker ({host}:{port})",
                "path": path,
                "aircraft_count": len(json_data["aircraft"]),
                "last_update": json_data.get("now"),
            }

    except asyncio.TimeoutError:
        raise ConnectionTimeout(
            f"Timed out connecting to {host}:{port}"
        )
    except aiohttp.ClientConnectorError as err:
        if isinstance(err.os_error, ConnectionRefusedError):
            raise ConnectionRefused(
                f"Connection refused by {host}:{port}"
            )
        err_msg = str(err).lower()
        if "not found" in err_msg or "not known" in err_msg or "nodename" in err_msg:
            raise CannotResolve(
                f"Cannot resolve hostname: {host}"
            )
        raise CannotConnect(f"Network error connecting to {host}:{port}: {err}")
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Network error connecting to {host}:{port}: {err}")
    except Exception as err:
        _LOGGER.exception("Unexpected error validating ADSB connection")
        raise CannotConnect(f"Unexpected error: {err}")

    raise last_error



# notify services that aren't a device or a group of devices
_NOTIFY_SERVICE_SKIP = {"notify", "send_message", "persistent_notification"}


def _notify_targets(hass: HomeAssistant) -> list[str]:
    """Notify services to offer: mobile_app_* first, then groups and others."""
    services = hass.services.async_services().get("notify", {})
    names = [n for n in services if n not in _NOTIFY_SERVICE_SKIP]
    return sorted(names, key=lambda n: (not n.startswith("mobile_app_"), n))


def _as_list(value) -> list[str]:
    """Stored notification target(s) as a list (older entries hold a string)."""
    if isinstance(value, str):
        return [value] if value else []
    return [v for v in (value or []) if v]


def _notify_selector(hass: HomeAssistant, current):
    """Multi-select of notify services; keeps a stored name even if it's gone."""
    selected = _as_list(current)
    options = {name: f"notify.{name}" for name in _notify_targets(hass)}
    for name in selected:
        options.setdefault(name, f"notify.{name} (not currently available)")
    return vol.Optional(CONF_NOTIFICATION_DEVICE, default=selected), cv.multi_select(options)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADSB Aircraft Tracker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                # Create unique entry ID based on host:port
                host = user_input[CONF_ADSB_HOST]
                port = user_input[CONF_ADSB_PORT]
                unique_id = f"{host}:{port}"

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Store the basic config and validation info, pinning the
                # data path that answered so the coordinator doesn't re-probe
                self._user_input = {**user_input, CONF_ADSB_PATH: info["path"]}
                # The range was typed in Home Assistant's distance unit;
                # it is stored in miles
                limit = user_input.get(CONF_DISTANCE_LIMIT, 0)
                self._user_input[CONF_DISTANCE_LIMIT] = _edited(
                    limit, 0, 0, _setup_units(self.hass).distance_from_display
                )
                self._title = info["title"]
                self._validation_info = info
                return await self.async_step_summary()

            except ConnectionRefused:
                errors["base"] = "connection_refused"
            except ConnectionTimeout:
                errors["base"] = "timeout"
            except CannotResolve:
                errors[CONF_ADSB_HOST] = "cannot_resolve"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except InvalidADSBData:
                errors["base"] = "invalid_adsb_data"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_data_schema(self.hass),
            errors=errors,
            description_placeholders={
                "distance_unit": _setup_units(self.hass).distance_name,
            },
        )

    async def async_step_summary(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show connection summary and setup choice."""
        if user_input is not None:
            if user_input.get("setup_choice") == "configure_now":
                return await self.async_step_notifications()
            else:
                # Create entry with minimal configuration
                return self.async_create_entry(
                    title=self._title,
                    data=self._user_input,
                )

        # Build summary information
        info = self._validation_info
        aircraft_count = info.get("aircraft_count", 0)
        last_update = info.get("last_update")

        summary_text = f"✅ **Connection Successful!**\n\n"
        summary_text += f"🛜 **Found:** {aircraft_count} aircraft currently tracked\n"
        if last_update:
            summary_text += f"🕐 **Last Update:** {last_update}\n"
        summary_text += f"📡 **Source:** {self._user_input[CONF_ADSB_HOST]}:{self._user_input[CONF_ADSB_PORT]}{self._user_input[CONF_ADSB_PATH]}\n\n"
        summary_text += "You can set up notifications and alerts now, or configure them later in the integration options."

        schema = vol.Schema({
            vol.Required("setup_choice", default="configure_later"): vol.In({
                "configure_now": "Configure notifications now",
                "configure_later": "Finish setup (configure notifications later)"
            })
        })

        return self.async_show_form(
            step_id="summary",
            data_schema=schema,
            description_placeholders={"summary_text": summary_text}
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle notification configuration during initial setup."""
        if user_input is not None:
            # Combine basic config with notification settings
            final_data = {**self._user_input, **user_input}
            return self.async_create_entry(
                title=self._title,
                data=final_data,
            )

        _notify_key, _notify_sel = _notify_selector(self.hass, [])

        # Create simplified schema focusing on key notification settings
        notifications_schema = vol.Schema(
            {
                _notify_key: _notify_sel,
                vol.Optional(CONF_EXTERNAL_URL, default=""): str,
                vol.Optional(CONF_MILITARY_NOTIFICATIONS, default=DEFAULT_MILITARY_NOTIFICATIONS): bool,
                vol.Optional(CONF_EMERGENCY_NOTIFICATIONS, default=DEFAULT_EMERGENCY_NOTIFICATIONS): bool,
                vol.Optional(CONF_CLOSE_AIRCRAFT_ENABLED, default=DEFAULT_CLOSE_AIRCRAFT_ENABLED): bool,
                vol.Optional(CONF_OVERHEAD_ENABLED, default=DEFAULT_OVERHEAD_ENABLED): bool,
            }
        )

        return self.async_show_form(
            step_id="notifications",
            data_schema=notifications_schema,
            description_placeholders=URL_TOKEN_PLACEHOLDERS,
        )




# The external-URL help text shows the literal tokens {hex}, {flight} and
# {registration}. The frontend treats braces in translations as placeholders
# and logs MISSING_VALUE for each one, so hand them back as themselves.
URL_TOKEN_PLACEHOLDERS = {key: "{" + key + "}" for key in ("hex", "flight", "registration")}


def _overhead_guide(angle: float, units: UnitSystem) -> str:
    """Markdown shown under the overhead angle field: how narrow the cone is.

    A diagram of the cone at a few angles, then the numbers for the angle
    currently saved (the dialog can't redraw while the field is edited).
    """
    # Round example heights in whichever altitude unit is shown
    heights = (3000, 10000, 35000) if units.altitude_factor == 1 else (1000, 3000, 10000)

    def across(height: int) -> str:
        return units.format_distance(cone_footprint_mi(angle, height / units.altitude_factor))

    def at(height: int) -> str:
        return f"{height:,} {units.altitude_label}"

    low, mid, high = heights
    share = cone_sky_share(angle) * 100
    share_text = f"{share:.1f}" if share < 1 else f"{share:.0f}"
    return (
        f"![Cones 5°, 15°, 30° and 45° around straight up, seen from the side]"
        f"({OVERHEAD_DIAGRAM_URL}?v={INTEGRATION_VERSION})\n\n"
        f"Currently **{angle:g}°** from straight up: about {share_text}% of the sky. "
        f"That is a circle {across(low)} across for an aircraft at {at(low)}, "
        f"{across(mid)} at {at(mid)} and {across(high)} at {at(high)}. "
        f"For scale, a fist held at arm's length covers about 10°."
    )


def _alert_text_guide() -> str:
    """Markdown for the alert wording page: the tokens that can be used."""
    return "\n".join(f"- `{{{name}}}` {meaning}" for name, meaning in alert_text.TOKENS.items())


def _alert_text_defaults() -> dict[str, str]:
    """Option key -> template matching the built-in wording."""
    defaults: dict[str, str] = {}
    for kind, (title_key, message_key) in ALERT_TEXT_OPTIONS.items():
        defaults[title_key], defaults[message_key] = alert_text.DEFAULTS[kind]
    return defaults


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class ConnectionRefused(Exception):
    """Error to indicate the connection was actively refused."""


class ConnectionTimeout(Exception):
    """Error to indicate the connection timed out."""


class CannotResolve(Exception):
    """Error to indicate hostname resolution failed."""


class InvalidHost(Exception):
    """Error to indicate there is an invalid hostname."""


class InvalidADSBData(Exception):
    """Error to indicate invalid ADSB data format."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ADSB Aircraft Tracker."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial options step - choose configuration area."""
        if user_input is not None:
            if user_input.get("config_area") == "basic":
                return await self.async_step_basic_settings()
            if user_input.get("config_area") == "units":
                return await self.async_step_units()
            if user_input.get("config_area") == "text":
                return await self.async_step_alert_text()
            return await self.async_step_notifications_settings()

        schema = vol.Schema({
            vol.Required("config_area", default="basic"): vol.In({
                "basic": "📊 Basic Settings (connection, updates, range)",
                "units": "📐 Units (aeronautical, imperial or metric)",
                "notifications": "🔔 Notifications & Alerts",
                "text": "✏️ Alert Wording (your own titles and messages)",
            })
        })

        current_host = self.config_entry.data.get(CONF_ADSB_HOST, "unknown")
        current_port = self.config_entry.data.get(CONF_ADSB_PORT, DEFAULT_ADSB_PORT)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "current_host": current_host,
                "current_port": str(current_port),
            },
        )

    def _units(self) -> UnitSystem:
        """Units the threshold fields are shown and entered in."""
        return resolve_units(
            self.config_entry.options.get(CONF_UNITS, DEFAULT_UNITS),
            self.hass.config.units.length == "km",
        )

    async def async_step_units(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the units for distance, altitude and speed.

        A step of its own, so a unit change never shares a form with a
        threshold typed in the old unit.
        """
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )

        current = self.config_entry.options.get(CONF_UNITS, DEFAULT_UNITS)
        if current not in UNIT_PRESETS:
            current = DEFAULT_UNITS
        schema = vol.Schema({
            vol.Required(CONF_UNITS, default=current): SelectSelector(
                SelectSelectorConfig(
                    options=list(UNIT_PRESETS),
                    mode=SelectSelectorMode.LIST,
                    translation_key="units",
                )
            ),
        })
        return self.async_show_form(step_id="units", data_schema=schema)

    async def async_step_basic_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle basic connection and data settings."""
        errors: dict[str, str] = {}

        # Get current values from config entry
        current_data = self.config_entry.data
        current_options = self.config_entry.options

        # Get current values for display
        current_update = current_options.get(CONF_UPDATE_INTERVAL, current_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        current_distance = current_options.get(CONF_DISTANCE_LIMIT, current_data.get(CONF_DISTANCE_LIMIT, DEFAULT_DISTANCE_LIMIT))
        current_contact = current_options.get(CONF_ROUTE_API_CONTACT, "")
        current_photos = current_options.get(CONF_AIRCRAFT_PHOTOS, DEFAULT_AIRCRAFT_PHOTOS)

        # The range is stored in miles and shown in the chosen distance unit
        units = self._units()
        shown_distance = units.distance_to_display(current_distance, 0)
        max_distance = units.distance_to_display(MAX_DISTANCE_LIMIT_MI, 0)

        if user_input is not None:
            if CONF_DISTANCE_LIMIT in user_input:
                user_input[CONF_DISTANCE_LIMIT] = _edited(
                    user_input[CONF_DISTANCE_LIMIT], shown_distance,
                    current_distance, units.distance_from_display,
                )

            # Merge over existing options — each step only edits its own
            # fields, so replacing wholesale would wipe the other step's
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )

        basic_schema = vol.Schema(
            {
                vol.Optional(CONF_UPDATE_INTERVAL, default=current_update): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Optional(CONF_DISTANCE_LIMIT, default=shown_distance): vol.All(vol.Coerce(int), vol.Range(min=0, max=max_distance)),
                vol.Optional(CONF_ROUTE_API_CONTACT, description={"suggested_value": current_contact}): str,
                vol.Optional(CONF_AIRCRAFT_PHOTOS, default=current_photos): bool,
            }
        )

        return self.async_show_form(
            step_id="basic_settings",
            data_schema=basic_schema,
            errors=errors,
            description_placeholders={"distance_unit": units.distance_name},
        )

    async def async_step_notifications_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle notification and alert settings."""
        errors: dict[str, str] = {}

        # Get current values from config entry
        current_data = self.config_entry.data
        current_options = self.config_entry.options

        # Get current values for display
        current_device = current_options.get(CONF_NOTIFICATION_DEVICE, current_data.get(CONF_NOTIFICATION_DEVICE, []))
        _notify_key, _notify_sel = _notify_selector(self.hass, current_device)
        current_url = current_options.get(CONF_EXTERNAL_URL, "")

        # Get current notification settings
        current_military = current_options.get(CONF_MILITARY_NOTIFICATIONS, current_data.get(CONF_MILITARY_NOTIFICATIONS, DEFAULT_MILITARY_NOTIFICATIONS))
        current_close_enabled = current_options.get(CONF_CLOSE_AIRCRAFT_ENABLED, current_data.get(CONF_CLOSE_AIRCRAFT_ENABLED, DEFAULT_CLOSE_AIRCRAFT_ENABLED))
        current_close_distance = current_options.get(CONF_CLOSE_AIRCRAFT_DISTANCE, current_data.get(CONF_CLOSE_AIRCRAFT_DISTANCE, DEFAULT_CLOSE_AIRCRAFT_DISTANCE))
        current_close_altitude = current_options.get(CONF_CLOSE_AIRCRAFT_ALTITUDE, current_data.get(CONF_CLOSE_AIRCRAFT_ALTITUDE, DEFAULT_CLOSE_AIRCRAFT_ALTITUDE))
        current_emergency = current_options.get(CONF_EMERGENCY_NOTIFICATIONS, current_data.get(CONF_EMERGENCY_NOTIFICATIONS, DEFAULT_EMERGENCY_NOTIFICATIONS))

        current_overhead_enabled = current_options.get(CONF_OVERHEAD_ENABLED, current_data.get(CONF_OVERHEAD_ENABLED, DEFAULT_OVERHEAD_ENABLED))
        current_overhead_angle = current_options.get(CONF_OVERHEAD_ANGLE, current_data.get(CONF_OVERHEAD_ANGLE, DEFAULT_OVERHEAD_ANGLE))
        current_overhead_max_altitude = current_options.get(CONF_OVERHEAD_MAX_ALTITUDE, current_data.get(CONF_OVERHEAD_MAX_ALTITUDE, DEFAULT_OVERHEAD_MAX_ALTITUDE))

        # Thresholds are stored in miles and feet and shown in the chosen units
        units = self._units()
        shown_close_distance = units.distance_to_display(current_close_distance, 1)
        shown_close_altitude = units.altitude_to_display(current_close_altitude)
        shown_overhead_max_altitude = units.altitude_to_display(current_overhead_max_altitude)

        if user_input is not None:
            for key, shown, stored, convert in (
                (CONF_CLOSE_AIRCRAFT_DISTANCE, shown_close_distance,
                 current_close_distance, units.distance_from_display),
                (CONF_CLOSE_AIRCRAFT_ALTITUDE, shown_close_altitude,
                 current_close_altitude, units.altitude_from_display),
                (CONF_OVERHEAD_MAX_ALTITUDE, shown_overhead_max_altitude,
                 current_overhead_max_altitude, units.altitude_from_display),
            ):
                if key in user_input:
                    user_input[key] = _edited(user_input[key], shown, stored, convert)

            # Merge over existing options — each step only edits its own
            # fields, so replacing wholesale would wipe the other step's
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **user_input},
            )

        notifications_schema = vol.Schema(
            {
                _notify_key: _notify_sel,
                vol.Optional(CONF_EXTERNAL_URL, default=current_url): str,
                vol.Optional(CONF_MILITARY_NOTIFICATIONS, default=current_military): bool,
                vol.Optional(CONF_CLOSE_AIRCRAFT_ENABLED, default=current_close_enabled): bool,
                vol.Optional(CONF_CLOSE_AIRCRAFT_DISTANCE, default=shown_close_distance): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0.1, max=units.distance_to_display(MAX_CLOSE_DISTANCE_MI, 0)),
                ),
                vol.Optional(CONF_CLOSE_AIRCRAFT_ALTITUDE, default=shown_close_altitude): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=units.altitude_to_display(MIN_CLOSE_ALTITUDE_FT),
                        max=units.altitude_to_display(MAX_CLOSE_ALTITUDE_FT),
                    ),
                ),
                vol.Optional(CONF_OVERHEAD_ENABLED, default=current_overhead_enabled): bool,
                vol.Optional(CONF_OVERHEAD_ANGLE, default=current_overhead_angle): vol.All(vol.Coerce(float), vol.Range(min=1, max=60)),
                vol.Optional(CONF_OVERHEAD_MAX_ALTITUDE, default=shown_overhead_max_altitude): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=0, max=units.altitude_to_display(MAX_OVERHEAD_ALTITUDE_FT)),
                ),
                vol.Optional(CONF_EMERGENCY_NOTIFICATIONS, default=current_emergency): bool,
            }
        )

        return self.async_show_form(
            step_id="notifications_settings",
            data_schema=notifications_schema,
            errors=errors,
            # The frontend renders each field's help text as markdown with
            # these placeholders, which is how the cone diagram ends up
            # directly under the overhead angle field
            description_placeholders={
                **URL_TOKEN_PLACEHOLDERS,
                "overhead_guide": _overhead_guide(current_overhead_angle, units),
                "distance_unit": units.distance_name,
                "altitude_unit": units.altitude_name,
            },
        )

    async def async_step_alert_text(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Custom title and message for each kind of alert."""
        keys = [key for pair in ALERT_TEXT_OPTIONS.values() for key in pair]
        defaults = _alert_text_defaults()

        if user_input is not None:
            # A cleared field is left out of user_input; store it as empty so
            # the merge below doesn't keep the old wording
            texts = {key: (user_input.get(key) or "").strip() for key in keys}
            # Wording left as pre-filled is stored as "built-in", which keeps
            # following the built-in text if a later release changes it
            for key, default in defaults.items():
                if texts[key] == default:
                    texts[key] = ""
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, **texts},
            )

        current_options = self.config_entry.options
        fields: dict[Any, Any] = {}
        for title_key, message_key in ALERT_TEXT_OPTIONS.values():
            fields[vol.Optional(
                title_key, description={"suggested_value": current_options.get(title_key) or defaults[title_key]}
            )] = str
            fields[vol.Optional(
                message_key, description={"suggested_value": current_options.get(message_key) or defaults[message_key]}
            )] = TextSelector(TextSelectorConfig(multiline=True))

        return self.async_show_form(
            step_id="alert_text",
            data_schema=vol.Schema(fields),
            description_placeholders={"alert_text_guide": _alert_text_guide()},
        )
