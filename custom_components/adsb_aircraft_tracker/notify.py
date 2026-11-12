"""Notification system for ADSB Aircraft Tracker."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
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
    DEFAULT_MILITARY_NOTIFICATIONS,
    DEFAULT_CLOSE_AIRCRAFT_ENABLED,
    DEFAULT_CLOSE_AIRCRAFT_DISTANCE,
    DEFAULT_CLOSE_AIRCRAFT_ALTITUDE,
    DEFAULT_EMERGENCY_NOTIFICATIONS,
    DEFAULT_OVERHEAD_ENABLED,
    DEFAULT_OVERHEAD_ANGLE,
    DEFAULT_OVERHEAD_MAX_ALTITUDE,
    DEFAULT_UPDATE_INTERVAL,
)
from . import alert_text
from .coordinator import ADSBDataUpdateCoordinator
from .geo import distance_and_bearing, min_ground_distance_ahead, zenith_angle
from .tts_format import heading_to_cardinal
from .units import M_TO_FT

# One alert per aircraft pass: an aircraft that was overhead (or already got
# the low-aircraft alert) is not announced again for this long.
OVERHEAD_RENOTIFY_SECONDS = 300

_LOGGER = logging.getLogger(__name__)


class ADSBNotificationManager:
    """Manages notifications for ADSB aircraft events."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ADSBDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize notification manager."""
        self.hass = hass
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._last_military_aircraft: set[str] = set()
        self._last_close_aircraft: str | None = None
        self._last_emergency_aircraft: set[tuple[str, str]] = set()
        # hex -> monotonic time it was last inside the overhead cone
        self._overhead_last_seen: dict[str, float] = {}
        
    @property
    def notification_devices(self) -> list[str]:
        """Configured notify services (mobile devices and/or notify groups).

        Stored as a list since 1.8.0; older entries hold a single string.
        """
        value = (
            self.config_entry.options.get(CONF_NOTIFICATION_DEVICE) or
            self.config_entry.data.get(CONF_NOTIFICATION_DEVICE)
        )
        if isinstance(value, str):
            return [value] if value else []
        return [v for v in (value or []) if v]

    @property
    def notification_device(self) -> str | None:
        """First configured notify service (kept for callers of the old name)."""
        devices = self.notification_devices
        return devices[0] if devices else None
    
    @property 
    def external_url(self) -> str:
        """Get external ADSB URL for notifications."""
        return (
            self.config_entry.options.get(CONF_EXTERNAL_URL) or
            self.config_entry.data.get(CONF_EXTERNAL_URL) or
            f"http://{self.coordinator.adsb_host}:{self.coordinator.adsb_port}"
        )
    
    # Placeholders the external URL may contain, filled per aircraft
    URL_PLACEHOLDERS = ("hex", "flight", "registration", "tail")

    def aircraft_url(self, aircraft: dict[str, Any] | None) -> str:
        """External URL with {hex}/{flight}/{registration} filled in for this aircraft.

        Lets the tap-through open the aircraft itself on tar1090, adsb-3d or
        a public tracker, e.g. `https://my.tar1090/?icao={hex}`. An unknown
        value leaves an empty string; the URL is otherwise passed through.
        """
        url = self.external_url
        for key in self.URL_PLACEHOLDERS:
            token = "{" + key + "}"
            if token in url:
                value = (aircraft or {}).get(key) or ""
                url = url.replace(token, str(value).strip())
        return url

    @property
    def military_notifications_enabled(self) -> bool:
        """Check if military aircraft notifications are enabled."""
        return (
            self.config_entry.options.get(CONF_MILITARY_NOTIFICATIONS,
            self.config_entry.data.get(CONF_MILITARY_NOTIFICATIONS, DEFAULT_MILITARY_NOTIFICATIONS))
        )
    
    @property
    def close_aircraft_enabled(self) -> bool:
        """Check if close aircraft notifications are enabled."""
        return (
            self.config_entry.options.get(CONF_CLOSE_AIRCRAFT_ENABLED,
            self.config_entry.data.get(CONF_CLOSE_AIRCRAFT_ENABLED, DEFAULT_CLOSE_AIRCRAFT_ENABLED))
        )
    
    @property
    def close_aircraft_distance(self) -> float:
        """Get close aircraft distance threshold in miles."""
        value = self.config_entry.options.get(
            CONF_CLOSE_AIRCRAFT_DISTANCE,
            self.config_entry.data.get(CONF_CLOSE_AIRCRAFT_DISTANCE),
        )
        return DEFAULT_CLOSE_AIRCRAFT_DISTANCE if value is None else value

    @property
    def close_aircraft_altitude(self) -> int:
        """Get close aircraft altitude threshold in feet."""
        value = self.config_entry.options.get(
            CONF_CLOSE_AIRCRAFT_ALTITUDE,
            self.config_entry.data.get(CONF_CLOSE_AIRCRAFT_ALTITUDE),
        )
        return DEFAULT_CLOSE_AIRCRAFT_ALTITUDE if value is None else value
    
    @property
    def emergency_notifications_enabled(self) -> bool:
        """Check if emergency squawk notifications are enabled."""
        return (
            self.config_entry.options.get(CONF_EMERGENCY_NOTIFICATIONS,
            self.config_entry.data.get(CONF_EMERGENCY_NOTIFICATIONS, DEFAULT_EMERGENCY_NOTIFICATIONS))
        )
    
    @property
    def overhead_enabled(self) -> bool:
        """Check if overhead (straight up) notifications are enabled."""
        return (
            self.config_entry.options.get(CONF_OVERHEAD_ENABLED,
            self.config_entry.data.get(CONF_OVERHEAD_ENABLED, DEFAULT_OVERHEAD_ENABLED))
        )

    @property
    def overhead_angle(self) -> float:
        """Half-angle of the overhead cone, in degrees from straight up."""
        value = self.config_entry.options.get(
            CONF_OVERHEAD_ANGLE, self.config_entry.data.get(CONF_OVERHEAD_ANGLE)
        )
        return DEFAULT_OVERHEAD_ANGLE if value is None else value

    @property
    def overhead_max_altitude(self) -> int:
        """Ignore aircraft above this altitude (feet) for overhead alerts; 0 = no limit."""
        value = self.config_entry.options.get(
            CONF_OVERHEAD_MAX_ALTITUDE, self.config_entry.data.get(CONF_OVERHEAD_MAX_ALTITUDE)
        )
        return DEFAULT_OVERHEAD_MAX_ALTITUDE if value is None else value

    def _text_values(self, aircraft: dict[str, Any], **extra: Any) -> dict[str, str]:
        """Values for the {tokens} of a custom alert title or message."""
        flight = (aircraft.get("flight") or "").strip()
        tail = aircraft.get("tail") or ""
        if tail == "Unknown":
            tail = ""
        operator = aircraft.get("operator") or ""
        vrate = aircraft.get("vertical_rate_fpm") or 0
        units = self.coordinator.units
        values = {
            "name": flight or tail or "Unknown",
            "flight": flight,
            "tail": tail,
            "hex": aircraft.get("hex") or "",
            "type": aircraft.get("description") or "Unknown aircraft",
            "operator": "" if operator == "Unknown" else operator,
            "altitude": units.altitude_text(aircraft.get("altitude_ft")),
            "altitude_unit": units.altitude_label,
            "speed": units.speed_text(aircraft.get("speed_kts")),
            "speed_unit": units.speed_label,
            "distance": self.coordinator.format_distance(aircraft.get("distance_mi") or 0),
            "direction": heading_to_cardinal(aircraft.get("direction")) or "",
            "heading": heading_to_cardinal(aircraft.get("heading")) or "",
            "trend": "↗️" if vrate > 500 else "↘️" if vrate < -500 else "→",
            "emoji": "✈️",
            "angle": "",
            "where": "",
            "squawk": aircraft.get("squawk") or "",
            "emergency": "",
            "reasons": ", ".join(aircraft.get("_detection_reasons") or []),
        }
        values.update({key: str(value) for key, value in extra.items()})
        return values

    def _alert_text(
        self, kind: str, title: str, message: str, aircraft: dict[str, Any], **extra: Any
    ) -> tuple[str, str]:
        """The user's wording for this alert kind, or the built-in title/message."""
        title_key, message_key = ALERT_TEXT_OPTIONS[kind]
        options = self.config_entry.options
        if not (options.get(title_key) or options.get(message_key)):
            return title, message
        values = self._text_values(aircraft, **extra)
        return (
            alert_text.render(options.get(title_key), values) or title,
            alert_text.render(options.get(message_key), values) or message,
        )

    async def check_and_notify(
        self, aircraft_list: list[dict[str, Any]] | None = None
    ) -> None:
        """Check for notification conditions and send alerts.

        The coordinator passes the just-fetched aircraft list; falls back to
        the last stored data if called without one.
        """
        if not self.notification_devices:
            return
        if aircraft_list is None:
            if not self.coordinator.data:
                return
            aircraft_list = self.coordinator.data.get("aircraft", [])

        # Check for military aircraft notifications
        if self.military_notifications_enabled:
            await self._check_military_aircraft(aircraft_list)
        
        # Overhead runs before the low-aircraft check so that an aircraft
        # matching both gets one alert, not two
        if self.overhead_enabled:
            await self._check_overhead_aircraft(aircraft_list)

        # Check for close aircraft notifications  
        if self.close_aircraft_enabled:
            await self._check_close_aircraft(aircraft_list)
        
        # Check for emergency squawk notifications
        if self.emergency_notifications_enabled:
            await self._check_emergency_squawks(aircraft_list)
    
    async def _check_military_aircraft(self, aircraft_list: list[dict[str, Any]]) -> None:
        """Check and notify about military aircraft."""
        military_aircraft = self.coordinator.detect_military_aircraft(aircraft_list)

        current_military = {aircraft.get("hex") for aircraft in military_aircraft if aircraft.get("hex")}
        new_military = current_military - self._last_military_aircraft
        
        if new_military:
            for aircraft in military_aircraft:
                if aircraft.get("hex") in new_military:
                    await self._send_military_notification(aircraft)
        
        self._last_military_aircraft = current_military
    
    def _overhead_angles(
        self, plane: dict[str, Any], home_elevation_ft: float, lookahead_s: float
    ) -> tuple[float, float] | None:
        """(angle now, smallest angle over the next update) from straight up, in degrees.

        None for aircraft that can't be placed in the sky: on the ground, no
        position, or no known altitude above the home.
        """
        if plane.get("on_ground"):
            return None
        lat, lon = plane.get("latitude"), plane.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return None
        altitude = plane.get("altitude_geom")
        if not isinstance(altitude, (int, float)) or isinstance(altitude, bool):
            altitude = plane.get("altitude_ft") or 0
        if altitude <= 0:
            return None
        max_altitude = self.overhead_max_altitude
        if max_altitude and altitude > max_altitude:
            return None
        height = altitude - home_elevation_ft
        # Recomputed from the position: distance_mi is rounded to 0.1 mi,
        # too coarse for a narrow cone at low altitude
        distance, bearing = distance_and_bearing(
            self.hass.config.latitude, self.hass.config.longitude, lat, lon
        )
        now = zenith_angle(distance, height)
        if now is None:
            return None
        ahead = now
        heading, speed = plane.get("heading"), plane.get("speed_kts")
        if isinstance(heading, (int, float)) and isinstance(speed, (int, float)) and speed > 0:
            # A narrow cone is crossed in less than one update at low
            # altitude, so also test the straight path until the next one
            closest = min_ground_distance_ahead(distance, bearing, heading, speed, lookahead_s)
            ahead = zenith_angle(closest, height) or now
        return now, min(now, ahead)

    async def _check_overhead_aircraft(self, aircraft_list: list[dict[str, Any]]) -> None:
        """Notify when an aircraft is (about to be) nearly straight above the home.

        Once per pass: an aircraft is announced when it enters the cone and
        not again until it has been out of it for OVERHEAD_RENOTIFY_SECONDS,
        so a circling aircraft or a hovering helicopter alerts once.
        """
        now_ts = time.monotonic()
        threshold = self.overhead_angle
        home_elevation_ft = (self.hass.config.elevation or 0) * M_TO_FT
        interval = self.coordinator.update_interval
        lookahead_s = interval.total_seconds() if interval else DEFAULT_UPDATE_INTERVAL

        for plane in aircraft_list or []:
            hex_code = plane.get("hex")
            if not hex_code:
                continue
            angles = self._overhead_angles(plane, home_elevation_ft, lookahead_s)
            if angles is None or angles[1] > threshold:
                continue
            last = self._overhead_last_seen.get(hex_code)
            self._overhead_last_seen[hex_code] = now_ts
            if last is not None and now_ts - last <= OVERHEAD_RENOTIFY_SECONDS:
                continue
            if hex_code == self._last_close_aircraft:
                # Already announced by the low-aircraft alert on its way in
                continue
            await self._send_overhead_notification(plane, angles[0], angles[1], threshold)

        self._overhead_last_seen = {
            hex_code: seen
            for hex_code, seen in self._overhead_last_seen.items()
            if now_ts - seen <= OVERHEAD_RENOTIFY_SECONDS
        }

    async def _check_close_aircraft(self, aircraft_list: list[dict[str, Any]]) -> None:
        """Check and notify about very close/low aircraft."""
        if not aircraft_list:
            return
        
        distance_threshold = self.close_aircraft_distance
        altitude_threshold = self.close_aircraft_altitude
            
        # Find aircraft within configured distance and altitude thresholds
        # Note: Use "or 999" to handle None values (get() default only works if key is missing)
        close_aircraft = [
            plane for plane in aircraft_list
            if ((plane.get("distance_mi") or 999) <= distance_threshold and
                (plane.get("altitude_ft") or 50000) < altitude_threshold and
                (plane.get("distance_mi") or 999) > 0 and
                # the overhead alert already covered this aircraft
                plane.get("hex") not in self._overhead_last_seen)
        ]
        
        if not close_aircraft:
            self._last_close_aircraft = None
            return
            
        closest = min(close_aircraft, key=lambda x: x.get("distance_mi") or 999)
        closest_hex = closest.get("hex")
        
        # Only notify if it's a different aircraft
        if self._last_close_aircraft != closest_hex:
            await self._send_close_aircraft_notification(closest)
            self._last_close_aircraft = closest_hex
    
    async def _check_emergency_squawks(self, aircraft_list: list[dict[str, Any]]) -> None:
        """Check and notify about emergency squawk codes.

        Notifies once per (aircraft, squawk) — not every update cycle. A new
        emergency from the same aircraft, or the same code after it clears,
        notifies again.
        """
        emergency_squawks = {"7700", "7600", "7500"}
        current: set[tuple[str, str]] = set()

        for aircraft in aircraft_list:
            squawk = aircraft.get("squawk") or ""
            if squawk in emergency_squawks:
                key = (aircraft.get("hex") or "", squawk)
                current.add(key)
                if key not in self._last_emergency_aircraft:
                    await self._send_emergency_notification(aircraft)

        self._last_emergency_aircraft = current
    
    async def _send_military_notification(self, aircraft: dict[str, Any]) -> None:
        """Send military aircraft notification."""
        tail = aircraft.get("tail", "Unknown")
        flight = (aircraft.get("flight") or "").strip()
        distance = aircraft.get("distance_mi", 0)
        altitude = aircraft.get("altitude_ft", 0)
        units = self.coordinator.units
        description = aircraft.get("description", "Unknown aircraft")
        reasons = aircraft.get("_detection_reasons", [])
        speed = aircraft.get("speed_kts", 0)
        
        # Format vertical rate trend
        vrate = aircraft.get("vertical_rate_fpm", 0)
        trend = "↗️" if vrate > 500 else "↘️" if vrate < -500 else "→"
        
        identifier = flight if flight else tail
        
        message = (
            f"🪖 {identifier} at {units.altitude_text(altitude)}{units.altitude_label} {trend} {units.format_distance(distance)} away\n"
            f"Type: {description}\n"
            f"Speed: {units.speed_text(speed)}{units.speed_label}"
        )
        
        if flight:
            message += f"\nCallsign: {flight}"
            
        if reasons:
            message += f"\nDetected by: {', '.join(reasons)}"
        
        _LOGGER.debug("Sending military notification with external_url: %s", self.external_url)
        title, message = self._alert_text(
            "military", "🪖 MILITARY AIRCRAFT DETECTED", message, aircraft, emoji="🪖"
        )
        await self._send_notification(
            title=title,
            message=message,
            notification_icon="mdi:shield-airplane",
            color="green",
            image=aircraft.get("photo_large"),
            aircraft=aircraft,
        )
    
    async def _send_close_aircraft_notification(self, aircraft: dict[str, Any]) -> None:
        """Send close aircraft notification."""
        tail = aircraft.get("tail", "Unknown")
        flight = (aircraft.get("flight") or "").strip()
        distance = aircraft.get("distance_mi", 0)
        altitude = aircraft.get("altitude_ft", 0)
        units = self.coordinator.units
        speed = aircraft.get("speed_kts", 0)
        description = aircraft.get("description", "Unknown aircraft")
        
        vrate = aircraft.get("vertical_rate_fpm", 0)
        trend = "↗️" if vrate > 500 else "↘️" if vrate < -500 else "→"
        
        # Determine aircraft type emoji
        is_small = any(term in description.upper() for term in ["CESSNA", "PIPER", "BEECH", "CIRRUS"])
        is_heli = "HELICOPTER" in description.upper() or aircraft.get("aircraft_type", "").startswith("H")
        
        if is_heli:
            emoji = "🚁"
        elif vrate > 500:
            emoji = "🛫"
        elif vrate < -500:
            emoji = "🛬"
        elif is_small:
            emoji = "🛩️"
        else:
            emoji = "✈️"
        
        identifier = flight if flight else tail
        
        message = (
            f"{emoji} {identifier} at {units.altitude_text(altitude)}{units.altitude_label} {trend} {units.format_distance(distance)} away\n"
            f"{description} • {units.speed_text(speed)}{units.speed_label}"
        )
        
        if flight:
            message += f"\nFlight: {flight}"
        
        operator = aircraft.get("operator")
        if operator and operator != "Unknown":
            message += f"\nOperator: {operator}"
        
        title, message = self._alert_text(
            "close_aircraft", "✈️ LOW AIRCRAFT OVERHEAD", message, aircraft, emoji=emoji
        )
        await self._send_notification(
            title=title,
            message=message,
            notification_icon="mdi:airplane-alert",
            color="red",
            image=aircraft.get("photo_large"),
            aircraft=aircraft,
        )
    
    async def _send_overhead_notification(
        self, aircraft: dict[str, Any], angle_now: float, angle_min: float, threshold: float
    ) -> None:
        """Send the "look up" notification."""
        tail = aircraft.get("tail", "Unknown")
        flight = (aircraft.get("flight") or "").strip()
        altitude = aircraft.get("altitude_ft", 0)
        units = self.coordinator.units
        speed = aircraft.get("speed_kts", 0)
        description = aircraft.get("description", "Unknown aircraft")
        identifier = flight if flight else tail

        if angle_now <= threshold:
            where = f"{angle_now:.0f}° from straight up"
        else:
            # Caught by the look-ahead: still on its way in
            came_from = heading_to_cardinal(aircraft.get("direction"))
            where = f"about to pass within {angle_min:.0f}° of straight up"
            if came_from:
                where += f", coming from the {came_from}"

        message = (
            f"⬆️ {identifier} at {units.altitude_text(altitude)}{units.altitude_label}, {where}\n"
            f"{description} • {units.speed_text(speed)}{units.speed_label}"
        )
        going = heading_to_cardinal(aircraft.get("heading"))
        if going:
            message += f" heading {going}"

        operator = aircraft.get("operator")
        if operator and operator != "Unknown":
            message += f"\nOperator: {operator}"

        title, message = self._alert_text(
            "overhead", "⬆️ AIRCRAFT OVERHEAD", message, aircraft,
            emoji="⬆️", where=where, angle=f"{min(angle_now, angle_min):.0f}",
        )
        await self._send_notification(
            title=title,
            message=message,
            notification_icon="mdi:airplane",
            color="blue",
            image=aircraft.get("photo_large"),
            aircraft=aircraft,
        )

    async def _send_emergency_notification(self, aircraft: dict[str, Any]) -> None:
        """Send emergency squawk notification."""
        tail = aircraft.get("tail", "Unknown")
        flight = (aircraft.get("flight") or "").strip()
        squawk = aircraft.get("squawk", "")
        distance = aircraft.get("distance_mi", 0)
        
        emergency_types = {
            "7700": "GENERAL EMERGENCY",
            "7600": "RADIO FAILURE", 
            "7500": "HIJACK"
        }
        
        emergency_type = emergency_types.get(squawk, "EMERGENCY")
        identifier = flight if flight else tail
        
        message = f"{identifier} squawking {squawk} ({emergency_type}) at {self.coordinator.format_distance(distance)}"
        
        title, message = self._alert_text(
            "emergency", "⚠️ EMERGENCY SQUAWK", message, aircraft,
            emoji="⚠️", emergency=emergency_type,
        )
        await self._send_notification(
            title=title,
            message=message,
            notification_icon="mdi:alert",
            color="red",
            priority="high",
            image=aircraft.get("photo_large"),
            aircraft=aircraft,
        )
    
    async def _send_notification(
        self,
        title: str,
        message: str,
        notification_icon: str = "mdi:airplane",
        color: str = "blue",
        priority: str = "normal",
        image: str | None = None,
        aircraft: dict[str, Any] | None = None,
    ) -> None:
        """Send the notification to every configured notify service."""
        if not self.notification_devices:
            return
        url = self.aircraft_url(aircraft)
            
        data = {
            "title": title,
            "message": message,
            "data": {
                "notification_icon": notification_icon,
                "color": color,
                "clickAction": url,
                "actions": [
                    {
                        "action": "URI",
                        "title": "🗺️ View on ADSB Tracker",
                        "uri": url,
                    }
                ],
            }
        }

        if image:
            # Shown by the mobile apps as the expanded notification picture
            data["data"]["image"] = image

        _LOGGER.debug("Notification data with url %s: %s", url, data)
        
        if priority == "high":
            data["data"]["ttl"] = 0
            data["data"]["priority"] = "high"
        
        for service in self.notification_devices:
            try:
                await self.hass.services.async_call("notify", service, data)
                _LOGGER.debug("Sent notification to notify.%s: %s", service, title)
            except Exception as err:  # noqa: BLE001 - one bad target must not stop the others
                _LOGGER.error("Failed to send notification to notify.%s: %s", service, err)