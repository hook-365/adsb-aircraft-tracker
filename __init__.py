"""ADSB Aircraft Tracker integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.service import async_set_service_schema
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import ADSBDataUpdateCoordinator
from .notify import ADSBNotificationManager
from .database_updater import async_setup_database_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ADSB Aircraft Tracker from a config entry."""
    
    # Create data coordinator
    update_interval = timedelta(
        seconds=entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )
    
    coordinator = ADSBDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        update_interval=update_interval,
    )
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Create notification manager
    notification_manager = ADSBNotificationManager(hass, coordinator, entry)
    
    # Store coordinator and notification manager in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "notification_manager": notification_manager,
    }
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_setup_services(hass, entry, coordinator)
    
    # Set up database update services
    await async_setup_database_services(hass)
    
    # Set up notification monitoring
    coordinator.notification_manager = notification_manager
    
    return True


async def _async_setup_services(hass: HomeAssistant, entry: ConfigEntry, coordinator: ADSBDataUpdateCoordinator) -> None:
    """Set up integration services."""
    
    async def refresh_data_service(call: ServiceCall) -> None:
        """Handle refresh data service call."""
        _LOGGER.info("Manual refresh requested for ADSB data")
        await coordinator.async_request_refresh()
        
    async def test_military_detection_service(call: ServiceCall) -> dict:
        """Handle test military detection service call."""
        if not coordinator.data or not coordinator.data.get("aircraft"):
            return {"error": "No aircraft data available"}
        
        from .binary_sensor import ADSBMilitaryAircraftSensor
        
        temp_sensor = ADSBMilitaryAircraftSensor(coordinator, entry)
        aircraft_list = coordinator.data["aircraft"]
        military_aircraft = temp_sensor._detect_military_aircraft(aircraft_list)
        
        result = {
            "total_aircraft": len(aircraft_list),
            "military_detected": len(military_aircraft),
            "detection_method": "database_only",
            "military_aircraft": []
        }
        
        for aircraft in military_aircraft:
            result["military_aircraft"].append({
                "tail": aircraft.get("tail", "Unknown"),
                "flight": aircraft.get("flight", ""),
                "distance_mi": aircraft.get("distance_mi", 0),
                "detection_reasons": aircraft.get("_detection_reasons", []),
                "description": aircraft.get("description", ""),
            })
        
        _LOGGER.info("Military detection test: %d/%d aircraft detected", len(military_aircraft), len(aircraft_list))
        return result
    
    async def get_aircraft_details_service(call: ServiceCall) -> dict:
        """Handle get aircraft details service call."""
        hex_code = call.data.get("hex_code", "").lower()
        
        if not coordinator.data or not coordinator.data.get("aircraft"):
            return {"error": "No aircraft data available"}
        
        # Find aircraft by hex code
        for aircraft in coordinator.data["aircraft"]:
            if aircraft.get("hex", "").lower() == hex_code:
                return {
                    "found": True,
                    "aircraft": {
                        "hex": aircraft.get("hex"),
                        "tail": aircraft.get("tail"),
                        "flight": aircraft.get("flight"),
                        "distance_mi": aircraft.get("distance_mi"),
                        "altitude_ft": aircraft.get("altitude_ft"),
                        "speed_kts": aircraft.get("speed_kts"),
                        "heading": aircraft.get("heading"),
                        "aircraft_type": aircraft.get("aircraft_type"),
                        "description": aircraft.get("description"),
                        "operator": aircraft.get("operator"),
                        "squawk": aircraft.get("squawk"),
                        "emergency": aircraft.get("emergency"),
                        "latitude": aircraft.get("latitude"),
                        "longitude": aircraft.get("longitude"),
                    }
                }
        
        return {"found": False, "error": f"Aircraft with hex code {hex_code} not found"}
    
    async def load_military_database_service(call: ServiceCall) -> dict:
        """Handle manual military database loading service call."""
        military_sensor = coordinator.military_sensor
        if military_sensor:
            _LOGGER.info("Manual military database load requested")
            result = await military_sensor._load_military_database()
            return {
                "success": result,
                "database_size": len(military_sensor._military_database) if military_sensor._military_database else 0,
                "message": "Database loaded successfully" if result else "Database load failed"
            }
        else:
            return {"error": "Military sensor not available"}
    
    # Register services with the integration domain
    hass.services.async_register(
        DOMAIN,
        "refresh_data",
        refresh_data_service,
    )
    
    hass.services.async_register(
        DOMAIN,
        "test_military_detection",
        test_military_detection_service,
        supports_response=True,
    )
    
    hass.services.async_register(
        DOMAIN,
        "get_aircraft_details",
        get_aircraft_details_service,
        schema=vol.Schema({
            vol.Required("hex_code"): str,
        }),
        supports_response=True,
    )
    
    hass.services.async_register(
        DOMAIN,
        "load_military_database",
        load_military_database_service,
        supports_response=True,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)