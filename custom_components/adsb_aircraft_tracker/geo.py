"""Great-circle helpers for ADSB Aircraft Tracker."""
from __future__ import annotations

import math

EARTH_RADIUS_MI = 3958.8


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
