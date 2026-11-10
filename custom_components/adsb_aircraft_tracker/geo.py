"""Great-circle helpers for ADSB Aircraft Tracker."""
from __future__ import annotations

import math

EARTH_RADIUS_MI = 3958.8
FT_PER_MI = 5280.0
KT_TO_MI_PER_S = 1.15078 / 3600


def distance_and_bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> tuple[float, float]:
    """Great-circle distance (statute miles) and initial bearing (degrees)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    distance = 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return distance, bearing


def angle_between(a: float, b: float) -> float:
    """Smallest difference between two compass headings, 0-180 degrees."""
    return abs((a - b + 180) % 360 - 180)


def zenith_angle(ground_distance_mi: float, height_ft: float) -> float | None:
    """Degrees away from straight up for something at this ground distance and height.

    0 = directly above, 90 = on the horizon. None when the height is not
    above the observer.
    """
    if height_ft <= 0:
        return None
    return math.degrees(math.atan2(ground_distance_mi * FT_PER_MI, height_ft))


def min_ground_distance_ahead(
    distance_mi: float,
    bearing: float,
    heading: float,
    speed_kts: float,
    seconds: float,
) -> float:
    """Closest ground distance (miles) to the observer over the next `seconds`.

    The aircraft is `distance_mi` away on compass `bearing` from the observer
    and flies straight on `heading` at `speed_kts`. Flat-earth geometry,
    which is fine for the few miles this is used over.
    """
    b, h = math.radians(bearing), math.radians(heading)
    x, y = distance_mi * math.sin(b), distance_mi * math.cos(b)
    ux, uy = math.sin(h), math.cos(h)
    travel = max(speed_kts, 0) * KT_TO_MI_PER_S * max(seconds, 0)
    along = min(max(-(x * ux + y * uy), 0.0), travel)
    return math.hypot(x + ux * along, y + uy * along)


def cone_sky_share(angle: float) -> float:
    """Fraction of the visible sky inside a cone `angle` degrees around straight up."""
    return 1 - math.cos(math.radians(angle))


def cone_footprint_mi(angle: float, height_ft: float) -> float:
    """Diameter (miles) of the circle the cone covers at `height_ft` above the observer."""
    return 2 * height_ft * math.tan(math.radians(angle)) / FT_PER_MI
