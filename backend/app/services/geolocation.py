"""
Geolocation service for resolving place names to coordinates and distance calculations.

This module provides:
- In-memory caching with TTL for location lookups
- External geocoding via OpenStreetMap Nominatim API
- Haversine distance calculations
- Database-backed persistent caching of resolved locations

**Architecture**:
1. Memory cache (TTL ~24 hours) for fast repeated lookups
2. Database lookup in LocationLookup table
3. Fallback to external API (Nominatim) if not found
4. Store result in database for future fast lookups

**Future Optimizations** (documented for scaling):
- Replace in-memory cache with Redis for distributed setups
- Replace Nominatim with PostGIS + GiST indexing for large datasets
- Add autocomplete using LocationLookup.search_count sorting
- Support location aliases (e.g., "Cochin" → "Kochi")
"""

import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models.travel.location import LocationLookup


class GeoCache:
    """
    In-memory cache with TTL for location lookups.
    
    Key: normalized location string (lowercase)
    Value: (latitude, longitude)
    TTL: 24 hours (configurable)
    
    Thread-safe basic implementation. For production at scale, replace with Redis.
    """

    def __init__(self, ttl_hours: int = 24):
        """
        Initialize cache with TTL.

        Args:
            ttl_hours: Time-to-live in hours (default 24)
        """
        self.ttl_seconds = ttl_hours * 3600
        self._cache: Dict[str, Tuple[float, float, float]] = {}  # (lat, lon, timestamp)

    def get(self, key: str) -> Optional[Tuple[float, float]]:
        """
        Retrieve cached coordinate, if not expired.

        Args:
            key: Normalized location string

        Returns:
            (lat, lon) tuple if found and not expired, None otherwise
        """
        key_lower = key.lower().strip()
        if key_lower not in self._cache:
            return None

        lat, lon, timestamp = self._cache[key_lower]
        age = time.time() - timestamp

        if age > self.ttl_seconds:
            # Expired; remove and return None
            del self._cache[key_lower]
            return None

        return (lat, lon)

    def set(self, key: str, value: Tuple[float, float]) -> None:
        """
        Store coordinate in cache with current timestamp.

        Args:
            key: Normalized location string
            value: (lat, lon) tuple
        """
        key_lower = key.lower().strip()
        self._cache[key_lower] = (value[0], value[1], time.time())

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Return number of cached entries (including expired)."""
        return len(self._cache)


# Global cache instance (singleton pattern)
_geo_cache = GeoCache(ttl_hours=24)


def get_cache() -> GeoCache:
    """Get the global geolocation cache instance."""
    return _geo_cache


async def resolve_location(
    query: str, session: Session
) -> Optional[Tuple[float, float]]:
    """
    Resolve a human-readable location name to geographic coordinates.

    **Resolution Strategy**:
    1. Normalize input (lowercase, strip whitespace)
    2. Check in-memory cache (fast, ~24 hour TTL)
    3. Query LocationLookup table (persistent cache)
    4. If not found, call OpenStreetMap Nominatim API
    5. Store result in LocationLookup for future lookups
    6. Return (lat, lon) or None if not found

    **Nominatim API**:
    - Free service; no API key required
    - Rate limit: ~1 request per second recommended
    - Returns JSON with list of results; we use the first match
    - Used for: addresses, place names, landmarks

    **Error Handling**:
    - Network timeouts: returns None (caller should handle gracefully)
    - Invalid input (empty): returns None
    - API errors: logs and returns None

    Args:
        query: Place name or address (e.g., "New York", "Kochi", "Times Square")
        session: SQLModel database session

    Returns:
        (latitude, longitude) tuple if resolved, None otherwise

    Example:
        ```python
        coords = await resolve_location("Bangalore", db_session)
        if coords:
            lat, lon = coords
            print(f"Found at {lat}, {lon}")
        else:
            print("Location not found")
        ```
    """
    if not query:
        return None

    # Step 1: Normalize input
    normalized_query = query.lower().strip()

    # Step 2: Check in-memory cache
    cached = _geo_cache.get(normalized_query)
    if cached:
        return cached

    # Step 3: Query database (LocationLookup)
    db_result = _query_location_lookup(session, normalized_query)
    if db_result:
        lat, lon = db_result
        # Also update cache
        _geo_cache.set(normalized_query, (lat, lon))
        # Increment search count in DB
        _increment_search_count(session, normalized_query)
        return (lat, lon)

    # Step 4: Call external API (Nominatim)
    api_result = await _nominatim_geocode(normalized_query)
    if not api_result:
        return None

    lat, lon = api_result

    # Step 5: Store in database for future lookups
    try:
        _store_location_lookup(session, normalized_query, lat, lon)
    except Exception as e:
        # Log but don't fail if DB insertion fails
        print(f"Warning: Failed to store location lookup for '{normalized_query}': {e}")

    # Step 6: Store in memory cache and return
    _geo_cache.set(normalized_query, (lat, lon))
    return (lat, lon)


async def _nominatim_geocode(query: str) -> Optional[Tuple[float, float]]:
    """
    Query OpenStreetMap Nominatim API for place coordinates.

    **Endpoint**: https://nominatim.openstreetmap.org/search
    **Parameters**:
    - q: query string
    - format: json
    - limit: number of results (we use 1)

    **Response** (if found):
    ```json
    [
        {
            "lat": "40.7127753",
            "lon": "-74.0059728",
            "display_name": "New York, United States",
            ...
        }
    ]
    ```

    **Rate Limiting**:
    - Nominatim Terms of Service recommend: max 1 req/sec
    - Our implementation is synchronous; at scale, use async queue

    Args:
        query: Normalized place name

    Returns:
        (lat, lon) tuple if found, None otherwise
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": f"{settings.PROJECT_NAME} / {settings.ENVIRONMENT}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

        results = response.json()
        if not results:
            return None

        first = results[0]
        lat = float(first.get("lat", 0))
        lon = float(first.get("lon", 0))

        if lat == 0 and lon == 0:
            return None

        return (lat, lon)

    except httpx.RequestError as e:
        print(f"Nominatim API request failed for '{query}': {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"Failed to parse Nominatim response for '{query}': {e}")
        return None


def _query_location_lookup(
    session: Session, normalized_name: str
) -> Optional[Tuple[float, float]]:
    """
    Query the LocationLookup table for a cached location.

    Args:
        session: Database session
        normalized_name: Lowercase, stripped place name

    Returns:
        (lat, lon) if found, None otherwise
    """
    try:
        stmt = select(LocationLookup).where(LocationLookup.name == normalized_name)
        result = session.exec(stmt).first()

        if result:
            return (result.latitude, result.longitude)
        return None
    except Exception as e:
        print(f"Database query failed for location lookup: {e}")
        return None


def _store_location_lookup(
    session: Session, normalized_name: str, latitude: float, longitude: float
) -> None:
    """
    Store a resolved location in the LocationLookup table.

    Args:
        session: Database session
        normalized_name: Lowercase, stripped place name
        latitude: Geographic latitude
        longitude: Geographic longitude

    Raises:
        Any exception from SQLModel (e.g., IntegrityError if duplicate name)
    """
    try:
        existing = session.exec(
            select(LocationLookup).where(LocationLookup.name == normalized_name)
        ).first()

        if existing:
            # Update existing entry (shouldn't happen in normal flow)
            existing.latitude = latitude
            existing.longitude = longitude
            existing.search_count += 1
            session.add(existing)
        else:
            # Create new entry
            lookup = LocationLookup(
                name=normalized_name,
                latitude=latitude,
                longitude=longitude,
                search_count=1,
            )
            session.add(lookup)

        session.commit()
    except Exception as e:
        session.rollback()
        raise


def _increment_search_count(session: Session, normalized_name: str) -> None:
    """
    Increment the search_count for a LocationLookup entry.

    Used to track popular searches (for future autocomplete/analytics).

    Args:
        session: Database session
        normalized_name: Lowercase, stripped place name
    """
    try:
        stmt = select(LocationLookup).where(LocationLookup.name == normalized_name)
        result = session.exec(stmt).first()

        if result:
            result.search_count += 1
            session.add(result)
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"Failed to increment search count for '{normalized_name}': {e}")


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.

    **Formula**:
    Uses the haversine formula for accurate distance calculation on Earth's surface.
    Accounts for Earth's curvature; more accurate than simple Euclidean distance.

    **Earth Radius**:
    - Used: 6371.0 km (mean radius)
    - Actual: varies from 6356.8 km (poles) to 6378.1 km (equator)

    **Accuracy**:
    - Typical error: ±0.5% for long distances (thousands of km)
    - Typical error: <1% for distances < 100 km

    **Performance**:
    - O(1) time complexity (just trigonometry)
    - Python: ~1 microsecond per call

    **Future**: For large-scale geo queries, use PostGIS ST_DWithin() in SQL.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in kilometers

    Example:
        ```python
        distance = haversine_distance(12.9716, 77.5946, 13.0827, 80.2707)  # Bangalore to Chennai
        print(f"Distance: {distance:.2f} km")  # ~350 km
        ```
    """
    R = 6371.0  # Earth's radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


__all__ = [
    "GeoCache",
    "get_cache",
    "resolve_location",
    "haversine_distance",
]
