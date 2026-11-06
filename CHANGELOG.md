# Changelog

All notable changes to this integration are listed here, newest first.
The **Unreleased** section collects changes since the last release; the
release script turns it into the next version's entry and into the GitHub
release notes, which HACS shows when it offers the update.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/hook-365/adsb-aircraft-tracker/compare/v1.6.7...HEAD
[1.6.7]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.7
[1.6.6]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.6
[1.6.5]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.5
[1.6.4]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.4
[1.6.3]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.3
[1.6.2]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.2
[1.6.1]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.1
[1.6.0]: https://github.com/hook-365/adsb-aircraft-tracker/releases/tag/v1.6.0
