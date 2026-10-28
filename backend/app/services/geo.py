"""Geospatial helpers.

Offline-first: a small curated city/locality index is used to derive approximate
coordinates for matching. Online geocoding (Nominatim) is optional and disabled
by default. We only ever *display* approximate distances - never exact
coordinates or addresses.
"""
from __future__ import annotations

import math

# (lat, lng) for demo index. locality keys are suburb-level, city keys are city-level.
PLACES: dict[str, tuple[float, float]] = {
    # Hyderabad
    "gachibowli": (17.4401, 78.3486),
    "hitech city": (17.4451, 78.3772),
    "hi-tech city": (17.4451, 78.3772),
    "madhapur": (17.4483, 78.3915),
    "kondapur": (17.4625, 78.3633),
    "banjara hills": (17.4126, 78.4392),
    "secunderabad": (17.4399, 78.4983),
    "hyderabad": (17.3850, 78.4867),
    "lingampally": (17.4948, 78.3140),
    "kukatpally": (17.4849, 78.4138),
    # Other major cities
    "koramangala": (12.9352, 77.6245),
    "whitefield": (12.9698, 77.7500),
    "hevgh": (12.9719, 77.5931),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "pune": (18.5204, 73.8567),
    "kothrud": (18.5074, 73.8077),
    "baner": (18.5642, 73.7769),
    "mumbai": (19.0760, 72.8777),
    "andheri": (19.1136, 72.8697),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "dwarka": (28.5921, 77.0460),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "salt lake": (22.5757, 88.4342),
    "vijayawada": (16.5062, 80.6480),
    "warangal": (17.9689, 79.5941),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
}


def lookup_coords(city: str | None, locality: str | None = None) -> tuple[float, float] | None:
    """Best-effort coords for a city/locality pair using the local index."""
    def norm(s: str | None) -> str:
        return (s or "").strip().lower()
    loc = norm(locality)
    if loc and loc in PLACES:
        return PLACES[loc]
    cty = norm(city)
    if cty and cty in PLACES:
        return PLACES[cty]
    # token search: "Hyderabad, near Gachibowli" -> check locality tokens
    if loc:
        for token in loc.replace("near", " ").replace(",", " ").split():
            if token in PLACES:
                return PLACES[token]
    if cty:
        for token in cty.replace(",", " ").split():
            if token in PLACES:
                return PLACES[token]
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def distance_display(distance_km: float | None) -> str:
    if distance_km is None:
        return "distance unavailable"
    if distance_km < 1:
        return "< 1 km"
    return f"≈ {round(distance_km, 1)} km"
