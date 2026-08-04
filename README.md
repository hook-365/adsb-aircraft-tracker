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
3. **Update Interval**: How often to fetch data (default: `10` seconds)
4. **Distance Limit**: Aircraft range in miles (`0` = unlimited)

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

**Response:** *"I'm detecting 2 military aircraft. The closest is a Boeing KC 135 Stratotanker, 15 miles away, at 24,000 feet, heading northeast."*

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
| `BOEING 777-300ER` | *Boeing triple seven ER* | Colloquial spoken name |
| `EMBRAER ERJ-190` | *Embraer E190* | Colloquial designation |
| `UAL123` | *United 1 2 3* | Airline code expanded, digits spelled out |
| `DAL45` | *Delta 4 5* | Same pattern |
| `Piper PA-28 Cherokee` | *Piper PA 28 Cherokee* | Hyphen removed (prevents TTS saying "minus") |
| heading `225°` | *heading southwest* | 8-point cardinal compass |
| climbing `+1500 fpm` | *climbing through 12,000 feet* | Altitude phrased with vertical context |
| speed `450 kts` | *cruising at 450 knots* | "cruising" for faster aircraft |

### How It Works

- 7 intent handlers are registered with Home Assistant's Assist pipeline (hassil)
- Voice queries go directly through intent recognition — the LLM conversation agent is **not** involved
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
- **Attributes**: Complete details of the nearest aircraft (distance, altitude, speed, heading, type, operator, etc.)
- **Use**: Track the aircraft closest to your location

#### `sensor.adsb_nearest_5_aircraft`
- **Value**: Summary count (e.g., "5 aircraft detected")
- **Attributes**: `aircraft_1` through `aircraft_5` with full details for each
- **Use**: Display the closest aircraft in cards/dashboards
- *Note: installs that predate the top-5 expansion keep their original entity id (e.g. `sensor.adsb_nearest_5_aircraft`) — Home Assistant never renames existing entities*

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

## Examples

A quick Mushroom card to get started:

```yaml
type: custom:mushroom-template-card
entity: sensor.adsb_all_aircraft
primary: Aircraft Nearby
secondary: >-
  {{ states('sensor.adsb_all_aircraft') }} ·
  {{ state_attr('sensor.adsb_closest_aircraft', 'distance_display') }} closest
icon: mdi:airplane
icon_color: blue
```

**[→ EXAMPLES.md](EXAMPLES.md)** has the full collection — automation blueprints,
a complete Mushroom aircraft-tracker card, military alert cards, built-in-card
layouts, and gauges. Every example is tested against a live dashboard.

## Troubleshooting

### No Aircraft Data
- Verify your ADSB feeder is accessible at the configured IP/port
- Test the URL manually: `http://YOUR_IP:8085/data/aircraft.json`
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
