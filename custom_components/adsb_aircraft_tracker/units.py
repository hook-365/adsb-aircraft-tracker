"""Display units for ADSB Aircraft Tracker.

Everything is computed and stored in the units the feeder data arrives in:
statute miles (distance from home), feet and knots. A UnitSystem converts
at the edges only: text shown or spoken to the user, and the threshold
fields of the options dialog. The raw `distance_mi` / `altitude_ft` /
`speed_kts` attributes are never converted.

No Home Assistant imports, so this module can be exercised on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

KM_PER_MI = 1.60934
# readsb's r_dst is in nautical miles
NM_TO_MI = 1.15078
M_TO_FT = 3.28084
KMH_PER_KT = 1.852

UNITS_AUTO = "auto"
UNITS_AERONAUTICAL = "aeronautical"
UNITS_IMPERIAL = "imperial"
UNITS_METRIC = "metric"
UNIT_PRESETS = (UNITS_AUTO, UNITS_AERONAUTICAL, UNITS_IMPERIAL, UNITS_METRIC)


@dataclass(frozen=True)
class UnitSystem:
    """One unit per quantity: factor from the stored unit, label, spoken name."""

    distance_factor: float  # miles -> display unit
    distance_label: str
    distance_name: str
    altitude_factor: float  # feet -> display unit
    altitude_label: str
    altitude_name: str
    speed_factor: float  # knots -> display unit
    speed_label: str
    speed_name: str

    # -- distance ---------------------------------------------------------
    def format_distance(self, miles: float | None) -> str:
        """ "4.2 km"; "Unknown" for a missing (or zero) distance."""
        if miles is None or miles == 0:
            return "Unknown"
        return f"{miles * self.distance_factor:.1f} {self.distance_label}"

    def distance_to_display(self, miles: float, digits: int = 1) -> float:
        """Stored miles -> number for an options field."""
        value = round(miles * self.distance_factor, digits)
        return int(value) if digits == 0 else value

    def distance_from_display(self, value: float) -> float:
        """Number from an options field -> miles to store."""
        return round(value / self.distance_factor, 3)

    # -- altitude ---------------------------------------------------------
    def altitude_text(self, feet: float | None) -> str:
        """Bare number with thousands separator: "3,000"."""
        return f"{(feet or 0) * self.altitude_factor:,.0f}"

    def format_altitude(self, feet: float | None) -> str:
        """ "3,000 ft"."""
        return f"{self.altitude_text(feet)} {self.altitude_label}"

    def speak_altitude(self, feet: float) -> str:
        """ "3,000 feet"."""
        return f"{self.altitude_text(feet)} {self.altitude_name}"

    def altitude_to_display(self, feet: float) -> int:
        """Stored feet -> whole number for an options field."""
        return int(round(feet * self.altitude_factor))

    def altitude_from_display(self, value: float) -> int:
        """Number from an options field -> feet to store."""
        return int(round(value / self.altitude_factor))

    # -- speed ------------------------------------------------------------
    def speed_text(self, knots: float | None) -> str:
        """Bare whole number: "450"."""
        return f"{(knots or 0) * self.speed_factor:.0f}"

    def format_speed(self, knots: float | None) -> str:
        """ "450 kts"."""
        return f"{self.speed_text(knots)} {self.speed_label}"

    def speak_speed(self, knots: float) -> str:
        """ "450 knots"."""
        return f"{self.speed_text(knots)} {self.speed_name}"


_MILES = (1.0, "mi", "miles")
_KILOMETERS = (KM_PER_MI, "km", "kilometers")
_NAUTICAL_MILES = (1 / NM_TO_MI, "nm", "nautical miles")
_FEET = (1.0, "ft", "feet")
_METERS = (1 / M_TO_FT, "m", "meters")
_KNOTS = (1.0, "kts", "knots")
_MPH = (NM_TO_MI, "mph", "miles per hour")
_KMH = (KMH_PER_KT, "km/h", "kilometers per hour")

AERONAUTICAL = UnitSystem(*_NAUTICAL_MILES, *_FEET, *_KNOTS)
IMPERIAL = UnitSystem(*_MILES, *_FEET, *_MPH)
METRIC = UnitSystem(*_KILOMETERS, *_METERS, *_KMH)
# What the integration did before units were selectable: distance follows
# Home Assistant's unit system, altitude and speed stay aeronautical.
AUTO_HA_IMPERIAL = UnitSystem(*_MILES, *_FEET, *_KNOTS)
AUTO_HA_METRIC = UnitSystem(*_KILOMETERS, *_FEET, *_KNOTS)

_PRESETS = {
    UNITS_AERONAUTICAL: AERONAUTICAL,
    UNITS_IMPERIAL: IMPERIAL,
    UNITS_METRIC: METRIC,
}


def resolve(preset: str | None, ha_is_metric: bool) -> UnitSystem:
    """UnitSystem for a saved preset; unknown or "auto" follows Home Assistant."""
    if preset in _PRESETS:
        return _PRESETS[preset]
    return AUTO_HA_METRIC if ha_is_metric else AUTO_HA_IMPERIAL
