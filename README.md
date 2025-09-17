# ADSB Aircraft Tracker for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

A comprehensive Home Assistant integration for tracking aircraft using ADSB data from dump1090/tar1090 feeders.

## Features

🛩️ **Aircraft Tracking**
- Real-time aircraft monitoring within configurable distance
- Detailed aircraft information (tail number, flight, altitude, speed, type)
- Top 3 closest aircraft with comprehensive details

🪖 **Military Aircraft Detection**
- Database-only detection using verified tar1090-db military aircraft (16,896+ aircraft)
- Zero false positives - only confirmed military aircraft
- Detailed detection reasons for each aircraft
- Automatic database updates every 24 hours

📱 **Smart Notifications**
- Mobile app notifications for military aircraft
- Low altitude aircraft alerts
- Emergency squawk code notifications (7700/7600/7500)
- Customizable external ADSB URL links

🔧 **Advanced Features**
- Runtime configuration changes (no restart required)
- Custom services for testing and manual control
- Developer tools for debugging detection logic
- Comprehensive error handling and logging

## Requirements

- **Home Assistant** 2023.1 or newer
- **ADSB Feeder** (dump1090/tar1090) running on your network
- **Mobile App** (optional, for notifications)

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/hook-365/adsb-aircraft-tracker`
6. Select "Integration" as the category
7. Click "Add"
8. Find "ADSB Aircraft Tracker" in the integration list and install
9. Restart Home Assistant
10. Go to Settings → Devices & Services → Add Integration
11. Search for "ADSB Aircraft Tracker" and follow the setup

### Manual Installation

1. Download the latest release from [GitHub][releases]
2. Extract the files to your `custom_components/adsb_aircraft_tracker/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "ADSB Aircraft Tracker"

## Configuration

### Initial Setup

1. **ADSB Host**: IP address of your dump1090/tar1090 feeder (e.g., `192.168.1.100`)
2. **ADSB Port**: Port number (default: `8085`)
3. **Update Interval**: How often to fetch data (default: `10` seconds)
4. **Distance Limit**: Aircraft range in miles (`0` = unlimited)

### Advanced Options

After initial setup, click **CONFIGURE** on your integration to access advanced options:

- **Military Detection**: Always enabled with database-only detection
- **Notification Device**: Select your mobile device for alerts
- **External URL**: Custom ADSB website URL for notifications

## Entities

The integration creates the following entities:

### Sensors

#### `sensor.adsb_all_aircraft`
- **Value**: Total aircraft count (e.g., "5 aircraft" or "12 aircraft (closest: 2.1 mi)")
- **Attributes**: Complete details for all tracked aircraft with distance, altitude, speed, type, etc.
- **Use**: Overview of all aircraft in range

#### `sensor.adsb_closest_aircraft`
- **Value**: Closest aircraft identifier (flight number, tail, or hex)
- **Attributes**: Complete details of the nearest aircraft (distance, altitude, speed, heading, type, operator, etc.)
- **Use**: Track the aircraft closest to your location

#### `sensor.adsb_nearest_3_aircraft`
- **Value**: Summary count (e.g., "3 aircraft detected")
- **Attributes**: `aircraft_1`, `aircraft_2`, `aircraft_3` with full details for each
- **Use**: Display top 3 closest aircraft in cards/dashboards

#### `sensor.adsb_military_details`
- **Value**: Military detection summary (e.g., "Military aircraft detected: 2 aircraft")
- **Attributes**: Details of detected military aircraft with detection reasons
- **Use**: Monitor military aircraft activity

#### `sensor.adsb_military_database_status`
- **Value**: Number of military aircraft in database (e.g., "16543")
- **Attributes**: Database health, last update time, load status
- **Use**: Monitor military detection database

### Binary Sensors

#### `binary_sensor.adsb_military_aircraft_present`
- **Value**: `on` when military aircraft detected, `off` otherwise
- **Attributes**: Count and details of military aircraft detected
- **Use**: Trigger automations for military aircraft alerts

## Services

### Manual Control
```yaml
# Refresh aircraft data immediately
service: adsb_aircraft_tracker.refresh_data

# Test military detection with current data
service: adsb_aircraft_tracker.test_military_detection

# Get details for specific aircraft
service: adsb_aircraft_tracker.get_aircraft_details
data:
  hex_code: "abc123"
```

## Notifications

The integration automatically sends mobile notifications for:

### Military Aircraft
- **Trigger**: Military aircraft detected on radar
- **Message**: Aircraft details, distance, detection reasons
- **Action**: Tap to open ADSB tracker

### Low Aircraft
- **Trigger**: Aircraft within 1.5 miles and below 3000ft altitude
- **Message**: Aircraft type, altitude, distance  
- **Action**: Tap to open ADSB tracker

### Emergency Squawks
- **Trigger**: Aircraft broadcasting 7700, 7600, or 7500 codes
- **Message**: Emergency type and aircraft details
- **Action**: Tap to open ADSB tracker

## Automation Examples

### Military Aircraft Alert
```yaml
automation:
  - alias: "Military Aircraft Detection"
    trigger:
      - platform: state
        entity_id: binary_sensor.adsb_military_aircraft_present
        from: 'off'
        to: 'on'
    action:
      - service: notify.persistent_notification
        data:
          title: "Military Aircraft Detected"
          message: "{{ state_attr('sensor.adsb_military_details', 'summary') }}"

### Close Aircraft TTS
```yaml
automation:
  - alias: "Aircraft Overhead Announcement"
    trigger:
      - platform: numeric_state
        entity_id: sensor.adsb_closest_aircraft
        attribute: distance_mi
        below: 2
    condition:
      - condition: numeric_state
        entity_id: sensor.adsb_closest_aircraft  
        attribute: altitude_ft
        below: 3000
    action:
      - service: tts.speak
        data:
          message: "Aircraft {{ state_attr('sensor.adsb_closest_aircraft', 'tail') }} overhead at {{ state_attr('sensor.adsb_closest_aircraft', 'altitude_ft') }} feet"
```

## Dashboard Examples

### Complete Aircraft Tracker Card

Perfect for a comprehensive aircraft tracking dashboard using Mushroom cards:

```yaml
type: custom:stack-in-card
mode: vertical
cards:
  - type: custom:mushroom-template-card
    primary: Aircraft Tracker
    secondary: |
      {% set count = states('sensor.adsb_all_aircraft') %}
      {{ count }}
    icon: mdi:airplane
    icon_color: orange
    tap_action:
      action: url
      url_path: http://192.168.1.200:8085
  - type: markdown
    content: >
      {% set a1 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_1') %}
      {% set a2 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_2') %}
      {% set a3 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_3') %}

      ## Aircraft Details

      {% if a1 %}
      **1. {{ a1.tail }}** {% if a1.flight and a1.flight != a1.tail %}({{ a1.flight }}){% endif %}

      - {{ a1.description }}
      - Distance: {{ a1.distance_display }}
      - Altitude: {{ a1.altitude_ft }}ft
      - Speed: {{ a1.speed_kts }}kts
      - Operator: {{ a1.operator }}

      {% endif %}
      {% if a2 %}
      **2. {{ a2.tail }}** {% if a2.flight and a2.flight != a2.tail %}({{ a2.flight }}){% endif %}

      - {{ a2.description }}
      - Distance: {{ a2.distance_display }}
      - Altitude: {{ a2.altitude_ft }}ft
      - Speed: {{ a2.speed_kts }}kts
      - Operator: {{ a2.operator }}

      {% endif %}
      {% if a3 %}
      **3. {{ a3.tail }}** {% if a3.flight and a3.flight != a3.tail %}({{ a3.flight }}){% endif %}

      - {{ a3.description }}
      - Distance: {{ a3.distance_display }}
      - Altitude: {{ a3.altitude_ft }}ft
      - Speed: {{ a3.speed_kts }}kts
      - Operator: {{ a3.operator }}

      {% endif %}
  - type: custom:mushroom-chips-card
    chips:
      - type: template
        content: >-
          Closest: {{ state_attr('sensor.adsb_closest_aircraft', 'distance_display') }}
        icon: mdi:map-marker-distance
      - type: template
        content: "{{ state_attr('sensor.adsb_closest_aircraft', 'altitude_ft') }}ft"
        icon: mdi:altimeter
      - type: template
        content: View Map
        icon: mdi:radar
        tap_action:
          action: url
          url_path: http://192.168.1.200:8085
```

### Military Aircraft Alert Card

For monitoring military aircraft activity:

```yaml
type: custom:mushroom-template-card
primary: Military Aircraft
secondary: |
  {% if is_state('binary_sensor.adsb_military_aircraft_present', 'on') %}
    {{ state_attr('sensor.adsb_military_details', 'summary') }}
  {% else %}
    No military aircraft detected
  {% endif %}
icon: mdi:airplane-shield
icon_color: |
  {% if is_state('binary_sensor.adsb_military_aircraft_present', 'on') %}
    red
  {% else %}
    green
  {% endif %}
badge_icon: |
  {% if is_state('binary_sensor.adsb_military_aircraft_present', 'on') %}
    mdi:alert
  {% endif %}
badge_color: red
tap_action:
  action: more-info
  entity: sensor.adsb_military_details
```

### Simple Aircraft Counter

Minimal aircraft count display:

```yaml
type: custom:mushroom-entity-card
entity: sensor.adsb_all_aircraft
name: Aircraft Nearby
icon: mdi:airplane
icon_color: blue
secondary_info: |
  {{ state_attr('sensor.adsb_closest_aircraft', 'distance_display') }} closest
tap_action:
  action: url
  url_path: http://192.168.1.200:8085
```

### Database Status Monitoring

Monitor the military aircraft database health:

```yaml
type: custom:mushroom-entity-card
entity: sensor.adsb_military_database_status
name: Military Database
icon: mdi:database-check
icon_color: |
  {% if state_attr('sensor.adsb_military_database_status', 'database_loaded') %}
    green
  {% else %}
    red
  {% endif %}
secondary_info: |
  {{ state_attr('sensor.adsb_military_database_status', 'last_updated_friendly') }}
```

## Built-in Card Examples

If you prefer to use Home Assistant's built-in cards without custom components:

### Aircraft Overview with Built-in Cards

```yaml
type: vertical-stack
cards:
  - type: glance
    title: Aircraft Tracker
    entities:
      - entity: sensor.adsb_all_aircraft
        name: Total Aircraft
        icon: mdi:airplane
      - entity: sensor.adsb_closest_aircraft
        name: Closest Aircraft
        icon: mdi:airplane-marker
      - entity: binary_sensor.adsb_military_aircraft_present
        name: Military Present
        icon: mdi:airplane-shield
  - type: entities
    title: Closest Aircraft Details
    entities:
      - entity: sensor.adsb_closest_aircraft
        name: Aircraft
        secondary_info: |
          {% set attrs = state_attr('sensor.adsb_closest_aircraft', 'description') %}
          {{ attrs if attrs else 'No aircraft detected' }}
      - type: attribute
        entity: sensor.adsb_closest_aircraft
        attribute: distance_display
        name: Distance
        icon: mdi:map-marker-distance
      - type: attribute
        entity: sensor.adsb_closest_aircraft
        attribute: altitude_ft
        name: Altitude
        icon: mdi:altimeter
        suffix: ft
      - type: attribute
        entity: sensor.adsb_closest_aircraft
        attribute: speed_kts
        name: Speed
        icon: mdi:speedometer
        suffix: kts
  - type: markdown
    content: |
      {% set a1 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_1') %}
      {% set a2 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_2') %}
      {% set a3 = state_attr('sensor.adsb_nearest_3_aircraft', 'aircraft_3') %}

      ### Top 3 Aircraft

      {% if a1 %}
      **1. {{ a1.tail }}** {% if a1.flight %}({{ a1.flight }}){% endif %}
      📍 {{ a1.distance_display }} • ⬆️ {{ a1.altitude_ft }}ft • 🚀 {{ a1.speed_kts }}kts
      {{ a1.description }}
      {% endif %}

      {% if a2 %}
      **2. {{ a2.tail }}** {% if a2.flight %}({{ a2.flight }}){% endif %}
      📍 {{ a2.distance_display }} • ⬆️ {{ a2.altitude_ft }}ft • 🚀 {{ a2.speed_kts }}kts
      {{ a2.description }}
      {% endif %}

      {% if a3 %}
      **3. {{ a3.tail }}** {% if a3.flight %}({{ a3.flight }}){% endif %}
      📍 {{ a3.distance_display }} • ⬆️ {{ a3.altitude_ft }}ft • 🚀 {{ a3.speed_kts }}kts
      {{ a3.description }}
      {% endif %}

      {% if not a1 %}
      *No aircraft currently detected*
      {% endif %}
```

### Simple Entity Cards

Individual cards for each sensor:

```yaml
# Basic aircraft count
type: entity
entity: sensor.adsb_all_aircraft
name: Aircraft Nearby
icon: mdi:airplane

# Military aircraft alert
type: entity
entity: binary_sensor.adsb_military_aircraft_present
name: Military Aircraft
icon: mdi:airplane-shield
state_color: true

# Closest aircraft with details
type: entity
entity: sensor.adsb_closest_aircraft
name: Closest Aircraft
secondary_info: |
  {% set distance = state_attr('sensor.adsb_closest_aircraft', 'distance_display') %}
  {% set altitude = state_attr('sensor.adsb_closest_aircraft', 'altitude_ft') %}
  {{ distance }} • {{ altitude }}ft
```

### Statistics Card

Show aircraft statistics over time:

```yaml
type: statistics-graph
entities:
  - sensor.adsb_all_aircraft
title: Aircraft Count History
period: hour
stat_types:
  - mean
  - min
  - max
```

### Military Aircraft Alert Card

Built-in conditional card for military alerts:

```yaml
type: conditional
conditions:
  - entity: binary_sensor.adsb_military_aircraft_present
    state: "on"
card:
  type: markdown
  content: |
    ## 🚨 MILITARY AIRCRAFT DETECTED

    {{ state_attr('sensor.adsb_military_details', 'summary') }}

    {% set military = state_attr('sensor.adsb_military_details', 'military_1') %}
    {% if military %}
    **Aircraft:** {{ military.tail }}
    **Distance:** {{ military.distance_display }}
    **Altitude:** {{ military.altitude_ft }}ft
    **Type:** {{ military.description }}
    {% endif %}
```

### Gauge Cards for Aircraft Data

Visual gauges for aircraft metrics:

```yaml
type: horizontal-stack
cards:
  - type: gauge
    entity: sensor.adsb_all_aircraft
    name: Aircraft Count
    min: 0
    max: 50
    severity:
      green: 0
      yellow: 10
      red: 25
  - type: gauge
    entity: sensor.adsb_closest_aircraft
    attribute: distance_mi
    name: Closest Distance
    min: 0
    max: 20
    unit: mi
    severity:
      red: 0
      yellow: 5
      green: 10
  - type: gauge
    entity: sensor.adsb_closest_aircraft
    attribute: altitude_ft
    name: Closest Altitude
    min: 0
    max: 10000
    unit: ft
```

## Military Detection Logic

The integration uses a database-only approach for 100% accurate military aircraft detection:

### Detection Method
- **Primary Source**: tar1090-db military aircraft database (Mictronics)
- **Database Size**: 16,896+ verified military aircraft
- **Detection**: ICAO hex code lookup in verified military database only
- **Updates**: Automatic database refresh every 24 hours
- **Accuracy**: Zero false positives - only definitively military aircraft

### No Pattern Matching
Previous versions used pattern matching for callsigns, operators, and aircraft types. This has been completely removed to eliminate false positives. Only aircraft verified as military in the official database will trigger alerts.

## Troubleshooting

### No Aircraft Data
- Verify your ADSB feeder is accessible at the configured IP/port
- Test the URL manually: `http://YOUR_IP:8085/data/aircraft.json`
- Check Home Assistant logs for connection errors

### Military Detection Issues
- Use the `test_military_detection` service to debug
- Check `sensor.adsb_military_details` for detection reasons
- Monitor `sensor.adsb_military_database_status` for database health
- Use `load_military_database` service to manually refresh database

### Notifications Not Working
- Verify mobile app device is selected in options
- Check notification permissions on your mobile device
- Test notifications with other Home Assistant integrations

## Contributing

Contributions are welcome! Please check the [contribution guidelines](CONTRIBUTING.md).

## License

This project is under the [MIT License](LICENSE).

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[commits]: https://github.com/hook-365/adsb-aircraft-tracker/commits/main
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[releases]: https://github.com/hook-365/adsb-aircraft-tracker/releases