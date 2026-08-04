# Dashboard & Automation Examples

Tested examples for the [ADSB Aircraft Tracker](README.md) integration.
All cards were verified against a live Home Assistant dashboard.

**Entity id note:** fresh installs create `sensor.adsb_nearest_5_aircraft`
(attributes `aircraft_1`–`aircraft_5`). Installs that predate the top-5
expansion keep their original entity id (e.g. `sensor.adsb_nearest_3_aircraft`)
— adjust the examples to match yours.

Cards under "Dashboard Examples" use [Mushroom](https://github.com/piitaya/lovelace-mushroom)
and [stack-in-card](https://github.com/custom-cards/stack-in-card) from HACS;
the "Built-in Card Examples" section needs no custom cards.

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
        icon: mdi:airplane-shield
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
