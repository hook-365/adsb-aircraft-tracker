# ADSB Aircraft Tracker for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

A comprehensive Home Assistant integration for tracking aircraft using ADSB data from dump1090/tar1090 feeders.

## Features

🛩️ **Aircraft Tracking**
- Real-time aircraft monitoring within configurable distance
- Detailed aircraft information (tail number, flight, altitude, speed, type)
- Top 5 closest aircraft with comprehensive details
- Aircraft type database with 85,000+ aircraft models
- Distance and bearing measured from your Home Assistant home location, in real statute miles
- Registration and aircraft type filled in from the tar1090-db database when the feeder doesn't send them (PiAware/dump1090-fa, bridges)
- Flight route (origin/destination) for every aircraft with a callsign, as sensor attributes
- Works with any readsb-style `aircraft.json` source (tar1090, readsb, dump1090-fa/SkyAware, or bridges from other receivers); the data path is auto-detected

📱 **Smart Notifications**
- Mobile app notifications for specific aircraft types
- Low altitude aircraft alerts
- Emergency squawk code notifications (7700/7600/7500)
- Customizable external ADSB URL links

🗣️ **Voice / Assist Support**
- 7 voice intents with 77 sentence variations
- TTS-friendly output: colloquial model names, airline code expansion, no mispronounced hyphens
- Flight route lookup (origin/destination) via [adsb.im](https://adsb.im)
- Filter by type: helicopters, jets, turboprops, military
- Works with Home Assistant Assist and voice pipelines
- Exposed as LLM tools for AI conversation agents (Home Assistant 2026.8+)

🔧 **Advanced Features**
- Runtime configuration changes (no restart required)
- Custom services for testing and manual control
- Developer tools for debugging detection logic
- Comprehensive error handling and logging

## Requirements

- **Home Assistant** 2023.7 or newer (service response support)
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
3. **Data Path** (optional): Leave blank to auto-detect. Setup tries `/data/aircraft.json` (tar1090/readsb), `/tar1090/data/aircraft.json`, `/skyaware/data/aircraft.json`, `/dump1090-fa/data/aircraft.json`, `/dump1090/data/aircraft.json`, `/aircraft.json`, then `/`, and keeps the first one that returns aircraft JSON. Set it explicitly for adapters that serve data somewhere else.
4. **Update Interval**: How often to fetch data (default: `10` seconds)
5. **Distance Limit**: Aircraft range in miles (`0` = unlimited)

Any source that returns readsb-style JSON (a top-level `"aircraft"` list with `hex`, `lat`/`lon`, `alt_baro`, `gs`, `track`, `flight`) works, including bridges from other services. The content type doesn't matter; `text/plain` is accepted.

### Advanced Options

After initial setup, click **CONFIGURE** on your integration to access advanced options:

- **Notification Device**: Select your mobile device for alerts
- **External URL**: Custom ADSB website URL for notifications
- **Update Interval**: Adjust data refresh frequency
- **Distance Limit**: Set maximum tracking range

## Voice / Assist Support

Ask your Home Assistant voice assistant about aircraft overhead and get natural, TTS-friendly spoken responses.

### Setup

1. Go to **Developer Tools → Services**
2. Call `adsb_aircraft_tracker.install_sentences`
3. Restart Home Assistant

That's it — the custom sentences are installed and the intent handlers register automatically.

### Intents & Example Phrases

#### Identify Aircraft — `ADSBWhatPlane`
> "What plane is that?" · "What's flying overhead?" · "What's up there?" · "What kind of plane is that?" · "Identify that aircraft"

**Response:** *"That's United 1 2 3, a Boeing 738, flying from Chicago to Denver, about 4 miles away, climbing through 12,000 feet, heading southwest, cruising at 450 knots."*

#### Nearest Aircraft — `ADSBNearestAircraft`
> "What planes are nearby?" · "Any planes around?" · "What do you see flying?" · "What planes can you see?"

**Response:** *"I'm tracking 47 aircraft. The nearest are: United 1 2 3, 4 miles away, at 32,000 feet, heading southwest; Delta 4 5 6, 8 miles away, descending through 15,000 feet; and SkyWest 7 8 9, 12 miles away, at 24,000 feet."*

#### Military Status — `ADSBMilitaryStatus`
> "Any military planes nearby?" · "Are there any military aircraft?" · "Military aircraft status"

**Response:** *"I'm detecting 2 military aircraft. The closest is a Boeing K C 135 Stratotanker, 15 miles away, at 24,000 feet, heading northeast."*

#### Aircraft Count — `ADSBAircraftCount`
> "How many planes?" · "How many aircraft are you tracking?" · "How many planes are out there?"

**Response:** *"I'm currently tracking 47 aircraft. The closest is 4 miles away."*

#### Flight Route — `ADSBAircraftRoute`
> "Where is that plane going?" · "What's the flight route?" · "Where did that plane come from?"

**Response:** *"The closest aircraft, United 1 2 3, is flying from Chicago to Denver, about 4 miles away, at 32,000 feet."*

#### Filter by Type — `ADSBAircraftByType`
> "Any helicopter aircraft nearby?" · "Do you see any jet planes?" · "Any prop planes flying?"

*Sentences require an "aircraft"/"planes" anchor word after the type (e.g. "military planes", "jet aircraft") — bare wildcards like "any helicopters nearby" over-matched unrelated queries in hassil.*

Supported types: `helicopters`, `choppers`, `jets`, `airliners`, `turboprops`, `props`, `cessna`, `military`

**Response:** *"I can see 3 helicopters nearby. The closest is 2 miles away, at 1,500 feet."*

#### Superlative Queries — `ADSBAircraftSuperlative`
> "What is the fastest aircraft?" · "What plane is the highest?" · "Find the closest plane" · "Which aircraft is the slowest?"

Supported queries: `fastest`, `quickest`, `speediest`, `slowest`, `highest`, `lowest`, `closest`, `nearest`, `farthest`, `furthest`

**Response:** *"The fastest aircraft is United 1 2 3, a Boeing 738, cruising at 520 knots, about 8 miles away, at 36,000 feet, heading southwest."*

### TTS-Friendly Output

All voice responses are formatted for natural text-to-speech pronunciation:

| Raw Data | Spoken As | Why |
|----------|-----------|-----|
| `BOEING 737-800` | *Boeing 738* | Title case, colloquial name, no hyphen |
| `BOEING 777-300ER` | *Boeing triple seven E R* | Colloquial spoken name, letters spelled out |
| `EMBRAER ERJ-190` | *Embraer E190* | Colloquial designation |
| `UAL123` | *United 1 2 3* | Airline code expanded, digits spelled out |
| `DAL45` | *Delta 4 5* | Same pattern |
| `Piper PA-28 Cherokee` | *Piper P A 28 Cherokee* | Hyphen removed, letter groups spelled out (no "minus", no "pah") |
| heading `225°` | *heading southwest* | 8-point cardinal compass |
| climbing `+1500 fpm` | *climbing through 12,000 feet* | Altitude phrased with vertical context |
| speed `450 kts` | *cruising at 450 knots* | "cruising" for faster aircraft |

### How It Works

- 7 intent handlers are registered with Home Assistant's Assist pipeline (hassil)
- Voice queries that match a sentence go directly through intent recognition, without the LLM conversation agent
- With an LLM conversation agent (Home Assistant 2026.8+), the same intents are also offered to the model as Assist API tools, with descriptions written to help it pick the right one. Answers are identical to the sentence path. HA stopped exposing intents to LLMs automatically in 2026.8, so this needs version 1.5.0 or newer of this integration
- Flight route data (origin/destination) is fetched from [adsb.im](https://adsb.im) and cached for 4 hours
- Aircraft type filtering uses ICAO engine type, category, and description keyword matching
- Military detection uses the tar1090-db verified database (same as notification system)
- Can also be triggered from **Developer Tools → Conversation** for testing

## Entities

The integration creates the following entities:

### Sensors

#### `sensor.adsb_all_aircraft`
- **Value**: Total aircraft count (e.g., "5 aircraft" or "12 aircraft (closest: 2.1 mi)")
- **Attributes**: Complete details for all tracked aircraft with distance, altitude, speed, type, etc.
- **Use**: Overview of all aircraft in range

#### `sensor.adsb_closest_aircraft`
- **Value**: Closest aircraft identifier (flight number, tail, or hex)
- **Attributes**: Complete details of the nearest aircraft (distance, altitude, speed, heading, type, operator, etc.), plus its route (`route_origin`, `route_origin_name`, `route_destination`, `route_destination_name`) when [adsb.im](https://adsb.im) knows it. Routes are looked up for every aircraft with a callsign: new callsigns are batched into one request per poll and cached for 4 hours. Private/GA flights usually have no route
- **Use**: Track the aircraft closest to your location

#### `sensor.adsb_nearest_5_aircraft`
- **Value**: Summary count (e.g., "5 aircraft detected")
- **Attributes**: `aircraft_1` through `aircraft_5` with full details for each, including route fields
- **Use**: Display the closest aircraft in cards/dashboards
- *Note: installs that predate the top-5 expansion keep their original entity id (e.g. `sensor.adsb_nearest_3_aircraft`) — Home Assistant never renames existing entities*

#### `sensor.adsb_military_aircraft_details`
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

# Install voice assistant sentence triggers
service: adsb_aircraft_tracker.install_sentences

# Force a fresh military database download
service: adsb_aircraft_tracker.load_military_database

# Update the aircraft types database from tar1090-db
service: adsb_aircraft_tracker.update_aircraft_types_database
```

## Notifications

The integration automatically sends mobile notifications for:

### Military Aircraft
- **Trigger**: Military aircraft detected on radar
- **Message**: Aircraft details, distance, detection reasons
- **Action**: Tap to open ADSB tracker

### Low Aircraft
- **Trigger**: Aircraft within 2 miles and below 3,000 ft (both thresholds configurable in options)
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
          message: "{{ state_attr('sensor.adsb_military_aircraft_details', 'summary') }}"
```

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

## Dashboard Card

The integration ships its own dashboard card. There's nothing to install: it loads automatically with the integration.

1. Edit a dashboard → **Add card** → search for **ADSB Aircraft Tracker**
2. Pick your tracker (only needed if you have more than one feeder) and how many aircraft to show

It lists the nearest aircraft with callsign, tail, route, distance, altitude and speed, colors each plane by altitude, and flags military aircraft. The card finds your tracker's entities by itself, so it works whatever your entity IDs are.

```yaml
type: custom:adsb-aircraft-tracker-card
count: 5          # optional, 1-5
title: Aircraft   # optional
device_id: ...    # optional; the editor fills this in when you pick a tracker
```

## Dashboard Examples

Prefer to build your own? The YAML examples below use the default entity IDs. New installs (1.6.1+) get exactly these IDs. Installs set up earlier on Home Assistant 2026.x may have longer IDs with the device name in them (e.g. `sensor.adsb_tracker_192_168_1_100_adsb_all_aircraft`), a second feeder gets a `_2` suffix, and very old installs may have `sensor.adsb_nearest_3_aircraft`. Check **Settings → Entities** and swap in your own; Home Assistant never renames existing entities. You can also rename them there to match the examples. Each YAML block is one card.

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
      url_path: http://192.168.1.100:8080
  - type: markdown
    content: |
      {% set a1 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_1') %}
      {% set a2 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_2') %}
      {% set a3 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_3') %}

      ## Aircraft Details

      {% if a1 %}
      **1. {{ a1.tail }}** {% if a1.flight and a1.flight != a1.tail %}({{ a1.flight }}){% endif %}

      - {{ a1.description }}
      {%- if a1.route_origin %}
      - Route: {{ a1.route_origin_name }} ({{ a1.route_origin }}) → {{ a1.route_destination_name }} ({{ a1.route_destination }})
      {%- endif %}
      - Distance: {{ a1.distance_display }}
      - Altitude: {{ a1.altitude_ft }}ft
      - Speed: {{ a1.speed_kts }}kts
      {%- if a1.operator %}
      - Operator: {{ a1.operator }}
      {%- endif %}

      {% endif %}
      {% if a2 %}
      **2. {{ a2.tail }}** {% if a2.flight and a2.flight != a2.tail %}({{ a2.flight }}){% endif %}

      - {{ a2.description }}
      {%- if a2.route_origin %}
      - Route: {{ a2.route_origin_name }} ({{ a2.route_origin }}) → {{ a2.route_destination_name }} ({{ a2.route_destination }})
      {%- endif %}
      - Distance: {{ a2.distance_display }}
      - Altitude: {{ a2.altitude_ft }}ft
      - Speed: {{ a2.speed_kts }}kts
      {%- if a2.operator %}
      - Operator: {{ a2.operator }}
      {%- endif %}

      {% endif %}
      {% if a3 %}
      **3. {{ a3.tail }}** {% if a3.flight and a3.flight != a3.tail %}({{ a3.flight }}){% endif %}

      - {{ a3.description }}
      {%- if a3.route_origin %}
      - Route: {{ a3.route_origin_name }} ({{ a3.route_origin }}) → {{ a3.route_destination_name }} ({{ a3.route_destination }})
      {%- endif %}
      - Distance: {{ a3.distance_display }}
      - Altitude: {{ a3.altitude_ft }}ft
      - Speed: {{ a3.speed_kts }}kts
      {%- if a3.operator %}
      - Operator: {{ a3.operator }}
      {%- endif %}

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
          url_path: http://192.168.1.100:8080
```

### Military Aircraft Alert Card

For monitoring military aircraft activity:

```yaml
type: custom:mushroom-template-card
primary: Military Aircraft
secondary: |
  {% if is_state('binary_sensor.adsb_military_aircraft_present', 'on') %}
    {{ state_attr('sensor.adsb_military_aircraft_details', 'summary') }}
  {% else %}
    No military aircraft detected
  {% endif %}
icon: mdi:shield-airplane
icon_color: >-
  {{ 'red' if is_state('binary_sensor.adsb_military_aircraft_present', 'on') else 'green' }}
badge_icon: >-
  {{ 'mdi:alert' if is_state('binary_sensor.adsb_military_aircraft_present', 'on') else '' }}
badge_color: red
tap_action:
  action: more-info
  entity: sensor.adsb_military_aircraft_details
```

### Simple Aircraft Counter

Minimal aircraft count display:

```yaml
type: custom:mushroom-template-card
entity: sensor.adsb_all_aircraft
primary: Aircraft Nearby
secondary: >-
  {{ states('sensor.adsb_all_aircraft') }} ·
  {{ state_attr('sensor.adsb_closest_aircraft', 'distance_display') }} closest
icon: mdi:airplane
icon_color: blue
tap_action:
  action: url
  url_path: http://192.168.1.100:8080
```

### Database Status Monitoring

Monitor the military aircraft database health:

```yaml
type: custom:mushroom-template-card
entity: sensor.adsb_military_database_status
primary: Military Database
secondary: >-
  {{ states('sensor.adsb_military_database_status') }} aircraft ·
  {{ state_attr('sensor.adsb_military_database_status', 'last_updated_friendly') }}
icon: mdi:database-check
icon_color: >-
  {{ 'green' if state_attr('sensor.adsb_military_database_status', 'database_loaded') else 'red' }}
tap_action:
  action: more-info
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
        icon: mdi:shield-airplane
  - type: entities
    title: Closest Aircraft Details
    entities:
      - entity: sensor.adsb_closest_aircraft
        name: Aircraft
      - type: attribute
        entity: sensor.adsb_closest_aircraft
        attribute: description
        name: Type
        icon: mdi:airplane-search
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
      {% set a1 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_1') %}
      {% set a2 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_2') %}
      {% set a3 = state_attr('sensor.adsb_nearest_5_aircraft', 'aircraft_3') %}

      ### Top 3 Aircraft

      {% if a1 %}
      **1. {{ a1.tail }}** {% if a1.flight and a1.flight != a1.tail %}({{ a1.flight }}){% endif %}
      📍 {{ a1.distance_display }} • ⬆️ {{ a1.altitude_ft }}ft • 🚀 {{ a1.speed_kts }}kts
      {{ a1.description }}
      {%- if a1.route_origin %}
      ✈️ {{ a1.route_origin }} → {{ a1.route_destination }}
      {%- endif %}
      {% endif %}

      {% if a2 %}
      **2. {{ a2.tail }}** {% if a2.flight and a2.flight != a2.tail %}({{ a2.flight }}){% endif %}
      📍 {{ a2.distance_display }} • ⬆️ {{ a2.altitude_ft }}ft • 🚀 {{ a2.speed_kts }}kts
      {{ a2.description }}
      {%- if a2.route_origin %}
      ✈️ {{ a2.route_origin }} → {{ a2.route_destination }}
      {%- endif %}
      {% endif %}

      {% if a3 %}
      **3. {{ a3.tail }}** {% if a3.flight and a3.flight != a3.tail %}({{ a3.flight }}){% endif %}
      📍 {{ a3.distance_display }} • ⬆️ {{ a3.altitude_ft }}ft • 🚀 {{ a3.speed_kts }}kts
      {{ a3.description }}
      {%- if a3.route_origin %}
      ✈️ {{ a3.route_origin }} → {{ a3.route_destination }}
      {%- endif %}
      {% endif %}

      {% if not a1 %}
      *No aircraft currently detected*
      {% endif %}
```

### Simple Entity Cards

Individual cards for each sensor. Each block is a separate card.

Basic aircraft count:

```yaml
type: entity
entity: sensor.adsb_all_aircraft
name: Aircraft Nearby
icon: mdi:airplane
```

Military aircraft alert:

```yaml
type: entity
entity: binary_sensor.adsb_military_aircraft_present
name: Military Aircraft
icon: mdi:shield-airplane
state_color: true
```

Closest aircraft with distance and altitude:

```yaml
type: tile
entity: sensor.adsb_closest_aircraft
name: Closest Aircraft
icon: mdi:airplane-marker
state_content:
  - state
  - distance_display
  - altitude_ft
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

    {{ state_attr('sensor.adsb_military_aircraft_details', 'summary') }}

    {% set military = state_attr('sensor.adsb_military_aircraft_details', 'military_1') %}
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
    attribute: total_aircraft
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

## Troubleshooting

### No Aircraft Data
- Verify your ADSB feeder is accessible at the configured IP/port
- Test the URL manually: `http://YOUR_IP:8085/data/aircraft.json` (or wherever your source serves its JSON; see **Data Path** above)
- "None of the data paths returned aircraft data" means the host answered but not at any standard path. Enter your source's path in the **Data Path** field
- Check Home Assistant logs for connection errors

### Notifications Not Working
- Verify mobile app device is selected in options
- Check notification permissions on your mobile device
- Test notifications with other Home Assistant integrations

### Database Issues
- Check `sensor.adsb_military_database_status` for database health
- Use the `load_military_database` service to force a fresh database download
- The database also refreshes automatically every 24 hours

## Credits

This integration uses the following open-source databases and APIs:

- **[tar1090-db](https://github.com/Mictronics/readsb-protobuf)** by Mictronics - Military aircraft database with 16,896+ verified military aircraft ICAO hex codes
- **ICAO Aircraft Types Database** - Comprehensive aircraft type information for 85,000+ aircraft models
- **[adsb.im](https://adsb.im)** - Flight route API for origin/destination airport lookups

Voice/Assist support was inspired by [@nwithan8](https://github.com/nwithan8)'s [tutorial and concept](https://github.com/hook-365/adsb-aircraft-tracker/issues/1).

Special thanks to the ADSB community for maintaining these valuable resources.

## Contributing

Contributions are welcome! Please check the [contribution guidelines](CONTRIBUTING.md).

## License

This project is under the [MIT License](LICENSE).

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[commits]: https://github.com/hook-365/adsb-aircraft-tracker/commits/main
[license-shield]: https://img.shields.io/github/license/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/hook-365/adsb-aircraft-tracker.svg?style=for-the-badge
[releases]: https://github.com/hook-365/adsb-aircraft-tracker/releases
