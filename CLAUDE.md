# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing the Integration
```bash
# Run the integration test script (validates aircraft database and imports)
cd /storage/docker/homeassistant-services/config
python3 test_adsb_integration.py

# Test Home Assistant configuration with the integration
cd /storage/docker/homeassistant-services/config
python3 -m homeassistant --script check_config

# Test service registration in Home Assistant Developer Tools
# Use these service calls in Home Assistant UI:
service: adsb_aircraft_tracker.refresh_data
service: adsb_aircraft_tracker.test_military_detection  
service: adsb_aircraft_tracker.get_aircraft_details
data:
  hex_code: "abc123"
```

### Container Operations
```bash
# Restart Home Assistant to reload integration changes
docker restart homeassistant

# View Home Assistant logs for debugging
docker logs homeassistant -f --tail=50

# Access Home Assistant container for debugging
docker exec -it homeassistant /bin/bash
```

## Architecture Overview

### Core Components Architecture
The integration follows Home Assistant's standard patterns with these key components:

```
__init__.py              - Entry point, service registration, coordinator setup
├── coordinator.py       - Data fetching from ADSB source (/data/aircraft.json)
├── sensor.py           - Aircraft count, closest, top 3 aircraft entities  
├── binary_sensor.py    - Military aircraft detection logic
├── notify.py           - Push notifications for military/emergency aircraft
├── config_flow.py      - UI configuration flow with validation
└── database_updater.py - ICAO aircraft types database maintenance
```

### Data Flow Architecture
```
ADSB Source (tar1090/dump1090) → ADSBDataUpdateCoordinator → Entity Updates
    ↓                                        ↓                      ↓
aircraft.json endpoint              Military Detection         Notifications
(every 10s default)                Logic Processing           (Mobile Push)
```

### Military Detection System
**Database-Only Approach**: The integration uses STRICT database-only military detection to eliminate false positives.

- **Primary Source**: tar1090-db military aircraft database (Mictronics) - 16,896+ verified military aircraft
- **Detection Method**: ICAO hex code lookup in verified military database only
- **No Fallback**: Removed all pattern matching, callsigns, squawk codes, and operator detection
- **Accuracy**: 100% accurate - only aircraft definitively marked as military in database
- **Loading**: Database loads automatically during coordinator initialization (reliable)
- **Updates**: Database refreshes every 24 hours automatically
- **Fallback**: Binary sensor can still load database if coordinator fails

Detection logic in `binary_sensor.py:_is_military_aircraft()` now only checks database matches.

## Key Configuration Points

### Integration Options (Runtime Configurable)
- **ADSB Host/Port**: Connection to dump1090/tar1090 feeder
- **Update Interval**: Data fetch frequency (default: 10 seconds)
- **Distance Limit**: Aircraft range filter (0 = unlimited)
- **Military Detection**: Always enabled with configurable sensitivity
- **Notifications**: Device selection + external ADSB URL for links

### Critical Constants
- `const.py` contains all military detection databases:
  - `MILITARY_CALLSIGNS`: Tactical callsigns (REACH, KING, etc.)
  - `MILITARY_TYPE_CODES`: Aircraft type codes (KC135, F16, etc.) 
  - `MILITARY_OPERATORS`: Military organizations
  - `CIVILIAN_AIRLINES`: Exclusion list for false positive prevention

### Aircraft Data Enhancement
The integration enriches basic ADSB data with:
- Aircraft type descriptions from `icao_aircraft_types.json` (85k+ entries)
- Distance/bearing calculations from Home Assistant coordinates
- Military detection reasoning and confidence scoring

## Entity Structure

### Sensors Created
- `sensor.adsb_aircraft_count` - Simple count of aircraft in range
- `sensor.adsb_closest_aircraft` - Full details of nearest aircraft
- `sensor.adsb_top_aircraft` - Array of top 3 closest with all attributes
- `sensor.adsb_military_details` - Military detection summary and reasons
- `sensor.adsb_military_database_status` - Military database monitoring and status

### Binary Sensors
- `binary_sensor.adsb_military_aircraft_present` - Military aircraft detected flag

## Development Workflow

### Making Changes to Detection Logic
**Note**: Detection is now database-only. Pattern matching has been removed.
1. Military detection relies solely on tar1090-db database (16,896+ aircraft)
2. **Database Loading**: Coordinator loads database automatically on startup
3. **Fallback Loading**: Binary sensor can also load database if coordinator fails
4. Test using service: `adsb_aircraft_tracker.test_military_detection`
5. Monitor database health with `sensor.adsb_military_database_status`
6. **Manual Loading**: Use service `adsb_aircraft_tracker.load_military_database` if needed
7. Restart Home Assistant to reload integration changes

### Adding New Notification Types
1. Add notification logic to `notify.py:_check_for_notifications()`
2. Define trigger conditions and message formatting
3. Test with different aircraft scenarios via manual ADSB data

### Configuration Changes
1. Add new config options to `const.py` 
2. Update `config_flow.py` for UI configuration
3. Modify coordinator initialization in `__init__.py`
4. Update `strings.json` for UI text

## Integration with Home Assistant Environment

### Container Context
- Integration runs inside Home Assistant container
- Python 3.12.3 available for testing
- Access to Home Assistant core APIs and helper functions
- Configuration stored in `/config/custom_components/adsb_aircraft_tracker/`

### HACS Compatibility
- Configured for HACS custom repository installation
- Supports zip releases and automatic updates
- Minimum Home Assistant version: 2023.1.0
- IoT Class: Local Polling (no cloud dependencies)

### Service Integration
Three custom services are registered for developer/automation use:
- `refresh_data` - Manual data refresh trigger
- `test_military_detection` - Returns detection results for current data
- `get_aircraft_details` - Lookup specific aircraft by hex code

## Common Development Tasks

### Debugging Military Detection
Use the test service to analyze detection logic:
```yaml
service: adsb_aircraft_tracker.test_military_detection
# Returns: total_aircraft, military_detected, sensitivity, military_aircraft array
```

### Testing Configuration Changes  
The integration supports runtime configuration updates without restart through the config flow options.

### Validating Aircraft Database
The `test_adsb_integration.py` script validates the ICAO aircraft types database integrity and import functionality.

### Monitoring Military Database
The new database status sensor provides comprehensive monitoring:
```yaml
# Database monitoring in automations
entity_id: sensor.adsb_military_database_status
# Value: Number of military aircraft in database (e.g., 12,543)
# Attributes:
#   - database_loaded: true/false
#   - database_size: aircraft count
#   - last_updated: ISO timestamp
#   - last_updated_friendly: human readable time
#   - status: "OK" or error message
```

**Database Source**: Downloads from `https://raw.githubusercontent.com/Mictronics/readsb-protobuf/dev/webapp/src/db/aircrafts.json`

**Database Loading Architecture**:
- **Primary**: Coordinator loads database during initialization (`coordinator.py:_async_load_military_database()`)
- **Secondary**: Binary sensor loads database on first access or manually
- **Status**: Database status available through coordinator or binary sensor
- **Reliability**: Dual loading system ensures database availability

**Troubleshooting Database Issues**:
- Check `sensor.adsb_military_database_status` for load status and size
- Use service `adsb_aircraft_tracker.load_military_database` for manual loading
- Database updates every 24 hours automatically
- 30-second timeout for downloads
- Only aircraft with flag "10" (military) are imported from 700k+ total aircraft
- No internet = no updates, but cached database persists until restart