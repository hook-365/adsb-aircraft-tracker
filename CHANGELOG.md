# Changelog

All notable changes to this integration are listed here, newest first.
The **Unreleased** section collects changes since the last release; the
release script turns it into the next version's entry and into the GitHub
release notes, which HACS shows when it offers the update.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Dashboard cards no longer color aircraft by altitude.** The colored
  strip on the left edge of small photos is gone, and airplane icons use
  the theme's primary color instead of blue/orange by altitude band. The
  altitude is still shown as a number on every row.

### Fixed
- **Rows without a photo line up with the rest.** The airplane icon that
  stands in for a missing photo now takes the photo's width, so callsigns
  start at the same place on every row.

## [1.8.2] - 2026-11-10

### Added
- **Overhead alerts.** A new notification for aircraft almost straight above
  you, at any altitude: anything inside a cone around straight up. The angle
  defaults to 15° from straight up (about 3% of the sky) and is adjustable
  from 1° to 60°, with an optional maximum altitude. Off by default; enable
  it in Options → Notifications, where a diagram shows how narrow the cone
  is. Height is measured above your Home Assistant home elevation, the path
  to the next update is checked so fast low passes aren't missed, each
  aircraft alerts once per pass, and an aircraft that also triggers the low
  aircraft alert is announced once, not twice.
- **Your own alert wording.** A new Options → Alert Wording page takes a
  title and a message for each kind of alert (military, close aircraft,
  overhead, emergency), with tokens such as `{name}`, `{altitude}`,
  `{distance}` and `{type}` filled in per aircraft. The fields start with the
  built-in wording, and a line whose values are all unknown is left out.

## [1.8.1] - 2026-11-10

### Fixed
- **Altitude, speed and vertical rate from older dump1090 feeders.** Builds
  that use the legacy `aircraft.json` field names `altitude`, `speed` and
  `vert_rate` (including the dump1090 bundled in the Flightradar24 feeder
  image) showed 0 for all three. They are now read when the readsb names
  `alt_baro`, `gs` and `baro_rate` are absent. (#8)

## [1.8.0] - 2026-11-06

### Added
- **Alerts to several devices or a notify group.** Options → Notifications →
  "Devices for alerts" is now a multi-select, and it lists notify groups
  (`notify.family_alerts` style, from the `group` platform) as well as
  mobile-app phones. Every alert goes to each selected service; a failing
  one is logged and doesn't stop the others. Existing single-device setups
  keep working unchanged.
- **Alerts open the aircraft.** The external URL may contain `{hex}`,
  `{flight}` or `{registration}`, filled in per alert, so tapping opens
  that aircraft on tar1090, adsb-3d or a public tracker.

## [1.7.0] - 2026-11-06

### Added
- **Aircraft photos.** The closest-aircraft card shows a photo of the
  airframe, the nearest-aircraft list shows a thumbnail per row, and
  military, low-overhead and emergency notifications carry the picture.
  Photos come from [planespotters.net](https://www.planespotters.net)'s
  public API: one small request per newly seen airframe, nearest five and
  military only, cached for 24 hours (including "no photo", common for GA
  aircraft), with the same polite User-Agent and backoff as route lookups.
  Photographer credit and a link to the photo page are shown, as their
  terms ask. Sensor attributes gain `photo_thumbnail`, `photo_large`,
  `photo_link` and `photo_photographer`. Options → Basic settings →
  "Aircraft photos" turns it off (on by default).
- **Photo style per card.** A `photos` option (also in the visual editor):
  the closest-aircraft card takes `banner` (default), `thumbnail` or
  `none`; the nearest-aircraft and military cards take `thumbnail`
  (default) or `none`. Small photos keep the altitude color on their left
  edge and fall back to the airplane icon when there is no photo. Military
  rows in the details sensor carry the photo fields too. Cards added from
  the **Add card** picker come with the photo option filled in, and the
  picker descriptions mention photos.

### Fixed
- **Card script cache-busting.** The card URL now carries a content hash as
  well as the version, so a changed card loads without a hard refresh even
  when the version didn't change (dev builds, manual installs).

## [1.6.7] - 2026-11-05

### Changed
- **Brand icon is readable on light themes.** The bundled icon was white
  artwork on a transparent background, so it nearly vanished on light
  backgrounds. `icon.png` / `icon@2x.png` are now dark slate, and the white
  version ships as `dark_icon.png` / `dark_icon@2x.png`, which Home Assistant
  picks automatically in dark mode.

## [1.6.6] - 2026-10-30

### Changed
- **Logo says what the integration is.** The brand icon's subtitle read
  "ADSB Airplane Tracker"; it now reads "ADSB Aircraft Tracker", matching the
  integration name everywhere else. No functional changes.

## [1.6.5] - 2026-10-30

Addresses the HACS review feedback on hacs/default#9755.

### Changed
- The bundled aircraft-types database is now read through
  `async_add_executor_job`; the `aiofiles` import (not a core dependency) and
  its blocking fallback are gone.
- `install_sentences` and `update_aircraft_types_database` write into the
  config directory and are now admin-only services. `install_sentences` keeps
  its optional response.

No functional changes for existing installs: entities, attributes, voice
intents and all six services behave as before.

## [1.6.4] - 2026-10-28

### Fixed
- **One version number.** The device `sw_version` said 1.6.2 while the route
  User-Agent said 1.6.3, and two differently-behaving builds both reported
  1.6.3 to adsb.im (#7). `manifest.json` and `INTEGRATION_VERSION` are now
  written together by a release script and CI fails if they ever differ or
  don't match the tag.
- **Your contact, not ours.** The adsb.im User-Agent had the author's email
  hardcoded. New optional setting **Route lookup contact** (Configure → Basic
  Settings) is sent as
  `adsb-aircraft-tracker/<version> (+https://github.com/hook-365/adsb-aircraft-tracker; <your contact>)`;
  left empty, only the project URL is sent. adsb.im is a one-person hobby
  service and asks callers to identify themselves, so please fill it in.

## [1.6.3] - 2026-10-28

### Fixed
- **Flight routes were silently empty.** adsb.im's route API began refusing
  Home Assistant's default User-Agent, so every `route_origin` /
  `route_destination` attribute went null. The integration now identifies
  itself with its own User-Agent, uses plain http, collects unknown callsigns
  for 2 minutes and sends them in one request, and on a refusal logs a warning
  once and pauses lookups for 10 minutes (#7). Thanks to Dirk for running the
  service and for the clear request.
- **Recorder warnings about `sensor.adsb_all_aircraft`** (#6). The
  all-aircraft and military-details sensors' attributes are excluded from
  history; they stay live for templates, cards and voice tools.
- **"Intent … is being overwritten" on reload or reinstall** (#6). Intent
  handlers register once per Home Assistant process and are removed when the
  last config entry unloads. Thanks to @brian-r-ohern for the report.

## [1.6.2] - 2026-09-29

- Dashboard cards load reliably (card-registration race fixed).
- Flightradar24 receiver setup documented (FR24 bridge).

## [1.6.1] - 2026-09-29

- Four built-in dashboard cards in the **Add card** picker.
- Short suggested entity IDs for new installs that match the docs.

## [1.6.0] - 2026-09-28

- Distances in true statute miles.
- Tail number and aircraft type filled in from tar1090-db for PiAware/dump1090-fa feeders.
- Flight routes for every aircraft with a callsign.

Older releases: see the [GitHub releases page](https://github.com/hook-365/adsb-aircraft-tracker/releases).

[Unreleased]: https://github.com/hook-365/adsb-aircraft-tracker/compare/v1.8.2...HEAD
[1.8.2]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.8.2
[1.8.1]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.8.1
[1.8.0]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.8.0
[1.7.0]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.7.0
[1.6.7]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.7
[1.6.6]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.6
[1.6.5]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.5
[1.6.4]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.4
[1.6.3]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.3
[1.6.2]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.2
[1.6.1]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.1
[1.6.0]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.0
