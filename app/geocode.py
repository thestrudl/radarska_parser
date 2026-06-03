"""Address -> (lat, lon) geocoding via Nominatim, with in-process caching.

Fixes the operator-precedence/None bug in the original
``RadarAnalyzer.get_location_data``.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _geolocator() -> Nominatim:
    return Nominatim(user_agent=get_settings().nominatim_user_agent, timeout=10)


@lru_cache(maxsize=512)
def geocode(address: str) -> tuple[float, float] | None:
    """Return (lat, lon) for an address, or None if it can't be resolved."""
    try:
        result = _geolocator().geocode(address)
    except GeopyError as err:
        logger.warning("Geocoding failed for %r: %s", address, err)
        return None
    if result is None:
        return None
    return result.latitude, result.longitude
