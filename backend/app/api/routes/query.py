"""
Query endpoints for searching and filtering travel resources (stay units, cabs, drivers).

These endpoints provide flexible searching capabilities with support for:
- Amenity filtering (with AND semantics for multiple amenities)
- Price range filtering
- Passenger capacity filtering (pax_count)
- Location-based geographic searches (latitude/longitude with radius)
- Vehicle type filtering for cabs
- Pagination (limit and offset)

Authorization:
- /query/stay-providers: superuser or agency staff only
- /query/units: superuser or agency staff only
- /query/cabs: public (no auth required)
- /query/drivers: public (no auth required)
- /query/stay-units-near: superuser or agency staff only
"""

import uuid
from typing import Any, List

from app.schemas.provider import PublicStayProviderList, StayProviderPublic
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app import crud
from app.schemas.provider.stays import (
    UnitsList,
)
from app.schemas.provider.cab import CabsList, DriversList
from app.api.routes.agency import is_agency_staff
from app.models.travel.enums import VehicleType

router = APIRouter(prefix="/query", tags=["query"])


# Search endpoint for stay providers with flexible filtering:
@router.get("/stay-providers", response_model=PublicStayProviderList)
def list_stay_providers(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    location_id: uuid.UUID = Query(default=None, description="Filter by location ID"),
    min_price: int = Query(default=None, ge=0, description="Minimum room rate to filter units"),
    max_price: int = Query(default=None, ge=0, description="Maximum room rate to filter units"),
    pax_count: int = Query(default=None, ge=1, description="Minimum occupancy required: filters providers with units that can accommodate pax_count guests"),
    amenities: List[str] = Query(default=None, description="List of required amenities (AND semantics: provider units must have ALL listed amenities)"),
    min_rating: float = Query(default=None, ge=0.0, le=5.0, description="Minimum average rating filter (reserved for future use)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
) -> dict:
    """
    List stay providers with optional filtering by location, price, capacity, amenities, and more.
    
    **Authorization**: superuser or agency staff only.
    
    **Filtering Logic** (all optional, combined with AND logic):
    - `location_id`: Filter providers by their location ID
    - `min_price` / `max_price`: Filter providers by unit room_rate (inclusive bounds)
    - `pax_count`: Filter providers with units that have sufficient capacity. A provider matches if:
      - Any of its units has max_occupancy >= pax_count, OR
      - The sum of all its units' max_occupancy >= pax_count
    - `amenities`: AND semantics. Provider must have units with ALL listed amenities to match.
      - Examples: 
        - `?amenities=wifi&amenities=ac` → providers whose units have both wifi AND ac
        - `?amenities=wifi,pool` → providers whose units have both wifi AND pool (auto-parsed)
        - Handles duplicates and whitespace gracefully
    - `min_rating`: Filter providers with average rating >= min_rating (reserved for future rating system)

    **Pagination**: Use `limit` and `offset` together for cursor-based pagination.

    **Response**: Returns `{ data: List[StayProviderPublic], count: int }` where count is matched providers on this page.
    
    **Example Queries**:
    ```
    GET /query/stay-providers?location_id=abc-123&min_price=100&max_price=500&pax_count=4
    GET /query/stay-providers?amenities=wifi&amenities=pool&amenities=parking
    GET /query/stay-providers?amenities=wifi,pool,parking
    ```
    """
    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay providers")

    # Fallback support to comma-separated value queries like '/stay-providers?amenities=wifi,pool'
    # small parser to convert comma-separated value to amenity list
    if amenities and len(amenities) == 1 and "," in amenities[0]:
        amenities = amenities[0].split(",")

    # normalize amenities: strip spaces, remove empty entries, dedupe repeated amenity
    if amenities:
        normalized = []
        for amenity in amenities:
            candidate = amenity.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        amenities = normalized or None

    providers, count = crud.list_stay_providers(
        session=session,
        location_id=str(location_id) if location_id else None,
        min_price=min_price,
        max_price=max_price,
        pax_count=pax_count,
        amenities=amenities,
        min_rating=min_rating,
        limit=limit,
        offset=offset,
    )

    stay_provider_list: list[StayProviderPublic] = []
    for provider in providers:
        if not provider.provider:
            continue
        stay_provider_list.append(
            StayProviderPublic(
                id=provider.provider.id,
                provider_name=provider.provider.provider_name,
                provider_type=provider.provider.provider_type,
                location_id=provider.provider.location_id,
                property_type=provider.property_type,
                room_count=provider.room_count,
                optimal_occupancy=provider.optimal_occupancy,
                max_occupancy=provider.max_occupancy,
            )
        )

    return PublicStayProviderList(data=stay_provider_list, count=count)


# This endpoint supports both the following ways of amenity url params
# GET /units?min_price=1000&max_price=5000&amenities=wifi&amenities=ac    (repeated params - returns units with ALL amenities)
# GET /units?amenities=wifi,pool                                           (comma-separated - auto-converts to same behavior)
@router.get("/units", response_model=UnitsList)
def list_stay_units(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    provider_id: uuid.UUID = Query(default=None, description="Filter by specific provider (optional)"),
    min_price: int = Query(default=None, description="Minimum room rate filter"),
    max_price: int = Query(default=None, description="Maximum room rate filter"),
    pax_count: int = Query(default=None, ge=1, description="Minimum occupancy required: filters units with max_occupancy >= pax_count OR total provider capacity >= pax_count"),
    amenities: List[str] = Query(default=None, description="List of required amenities (AND semantics: unit must have ALL listed amenities)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max number of results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip (for pagination)"),
) -> Any:
    """
    List available stay units with optional filtering and pagination.
    
    **Authorization**: superuser or agency staff only.
    
    **Filtering & Query Logic**:
    - `provider_id`: If provided, returns only units from that specific provider
    - `min_price` / `max_price`: Filters units by room_rate (inclusive bounds)
    - `pax_count`: Filters units with sufficient capacity. A unit matches if:
      - Its max_occupancy >= pax_count, OR
      - The sum of all units in the provider has total_capacity >= pax_count
    - `amenities`: AND semantics. Unit must have ALL listed amenities to match.
      - Examples: 
        - `?amenities=wifi&amenities=ac` → units with both wifi AND ac
        - `?amenities=wifi,pool` → units with both wifi AND pool (auto-parsed)
      - Handles duplicates and whitespace gracefully
    
    **Pagination**: Use `limit` and `offset` together for cursor-based pagination.
    
    **Response**: Returns `{ data: List[StayUnit], count: int }` where count is total matching units.
    """
    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay units")

    # Fallback support to comma-separated value queries like '/units?amenities=wifi,pool'
    # small parser to convert comma-separated value to amenity list
    if amenities and len(amenities) == 1 and "," in amenities[0]:
        amenities = amenities[0].split(",")

    # normalize amenities: strip spaces, remove empty entries, dedupe repeated amenity
    if amenities:
        normalized = []
        for amenity in amenities:
            candidate = amenity.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        amenities = normalized or None

    units, count = crud.list_stay_units(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        min_price=min_price,
        max_price=max_price,
        pax_count=pax_count,
        amenities=amenities,
        limit=limit,
        offset=offset,
    )
    return UnitsList(data=units, count=count)



@router.get("/cabs", response_model=CabsList)
def query_cabs(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None, description="Filter by specific cab provider"),
    vehicle_type: VehicleType = Query(default=None, description="Filter by vehicle type (e.g., SEDAN, SUV, HATCHBACK)"),
    lat: float = Query(default=None, description="Latitude: if provided with lon, filters cabs by provider location"),
    lon: float = Query(default=None, description="Longitude: if provided with lat, filters cabs by provider location"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers (used with lat/lon)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Query cabs with optional vehicle type and location-based provider filtering.
    
    **Authorization**: Public (no authentication required).
    
    **Filtering Logic**:
    - `provider_id`: Filter to a specific provider's cabs
    - `vehicle_type`: Filter by vehicle type string (e.g., SEDAN, SUV, HATCHBACK, etc.)
    - `lat` + `lon`: Geographic search. If both provided:
      - Uses bounding box around (lat, lon) with radius_km to find nearby providers
      - Returns cabs from those nearby providers (not a haversine distance to individual cabs)
    - `radius_km`: Controls the search radius when lat/lon are provided (default 5km)
    
    **Location-Based Search Note**: 
    This is a provider-level filter using provider location, not individual cab location.
    The bbox algorithm is fast but approximate (±0.1° accuracy per 11km).
    
    **Response**: `{ data: List[CabPublic], count: int }`
    """
    provider_ids = None
    if lat is not None and lon is not None:
        # Get provider IDs within the bounding box around the coordinates
        provider_ids = crud._providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    results, count = crud.list_cabs_query(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        provider_ids=provider_ids,
        vehicle_type=vehicle_type,
        limit=limit,
        offset=offset,
    )
    return {"data": results, "count": count}


@router.get("/drivers", response_model=DriversList)
def query_drivers(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None, description="Filter by specific driver provider"),
    lat: float = Query(default=None, description="Latitude: if provided with lon, filters drivers by provider location"),
    lon: float = Query(default=None, description="Longitude: if provided with lat, filters drivers by provider location"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers (used with lat/lon)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Query drivers with optional location-based provider filtering.
    
    **Authorization**: Public (no authentication required).
    
    **Filtering Logic**:
    - `provider_id`: Filter to a specific provider's drivers
    - `lat` + `lon`: Geographic search. If both provided:
      - Uses bounding box around (lat, lon) with radius_km to find nearby providers
      - Returns drivers from those nearby providers
    - `radius_km`: Controls the search radius when lat/lon are provided (default 5km)
    
    **Response**: `{ data: List[DriverPublic], count: int }`
    """
    provider_ids = None
    if lat is not None and lon is not None:
        # Get provider IDs within the bounding box around the coordinates
        provider_ids = crud._providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    results, count = crud.list_drivers_query(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        provider_ids=provider_ids,
        limit=limit,
        offset=offset,
    )
    return {"data": results, "count": count}


@router.get("/stay-units-near", response_model=UnitsList)
def query_stay_units_near(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    lat: float = Query(..., description="Latitude to search near (required)"),
    lon: float = Query(..., description="Longitude to search near (required)"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers"),
    amenity: str = Query(default=None, description="Single amenity to filter by (optional)"),
    min_price: int = Query(default=None, description="Minimum room rate filter"),
    max_price: int = Query(default=None, description="Maximum room rate filter"),
    sort_by_distance: bool = Query(default=False, description="If True, results sorted by haversine distance from (lat, lon)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Find stay units near a geographic point with optional filters.
    
    **Authorization**: superuser or agency staff only.
    
    **Geographic Search**:
    - `lat` / `lon`: Required. Center point for the search.
    - `radius_km`: Search radius in kilometers (default 5km).
    - Uses provider location as the anchor (providers within radius_km are candidates).
    - Results include all units from nearby providers.
    
    **Filtering**:
    - `amenity`: Single amenity filter (NOT the multi-amenity AND filtering of /units).
      - Example: `?amenity=wifi` returns units with wifi amenity.
    - `min_price` / `max_price`: Filters by room_rate (inclusive bounds).
    
    **Sorting**:
    - If `sort_by_distance=True`: Results are sorted by haversine distance from (lat, lon).
      - Note: Uses provider location for distance calculation.
      - This is computed in Python post-query for accuracy.
    
    **Response**: `{ data: List[StayUnit], count: int }` where count = len(data) after pagination.
    
    **Example**: 
    GET /query/stay-units-near?lat=12.97&lon=77.60&radius_km=10&amenity=wifi&min_price=100&max_price=500
    """
    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay units")

    units, count = crud.list_stay_units_by_location(
        session=session,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        amenity=amenity,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
        sort_by_distance=sort_by_distance,
    )
    return UnitsList(data=units, count=count)


__all__ = ["router"]
