"""
Query endpoints for searching and filtering travel resources (stay units, cabs, drivers).

These endpoints provide flexible searching capabilities with support for:
- Amenity filtering (with AND semantics for multiple amenities)
- Price range filtering
- Passenger capacity filtering (pax_count)
- Location-based geographic searches (latitude/longitude with radius)
- Location name resolution (e.g., "Bangalore", "New York") with automatic geocoding
- Vehicle type filtering for cabs
- Pagination (limit and offset)

Authorization:
- /query/stay-providers: superuser or agency staff only
- /query/units: superuser or agency staff only
- /query/cabs: public (no auth required)
- /query/drivers: public (no auth required)
- /query/stay-units-near: superuser or agency staff only

Location Resolution:
- Geographic endpoints support both lat/lon coordinates AND place names
- Provide either `location` (place name) OR `lat`/`lon` (coordinates)
- Automatic resolution via OpenStreetMap Nominatim API when location name provided
- Results cached in LocationLookup table for performance
- In-memory cache with 24-hour TTL
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
from app.services.geolocation import resolve_location, haversine_distance

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
    room_count: int = Query(default=None, ge=1, description="Minimum number of rooms required: filters providers with at least this many rooms"),
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
        room_count=room_count,
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
    room_count: int = Query(default=None, ge=1, description="Minimum number of rooms required: filters units from providers with at least this many rooms"),
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
    - `room_count`: Filters units from providers with at least this many rooms
    
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
        room_count=room_count,
        limit=limit,
        offset=offset,
    )
    return UnitsList(data=units, count=count)



@router.get("/cabs", response_model=CabsList)
async def query_cabs(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None, description="Filter by specific cab provider"),
    vehicle_type: VehicleType = Query(default=None, description="Filter by vehicle type (e.g., SEDAN, SUV, HATCHBACK)"),
    location: str = Query(default=None, description="Place name to search near (e.g., 'Bangalore', 'New York'). If provided, lat/lon are ignored."),
    lat: float = Query(default=None, description="Latitude: if provided with lon (and location not set), filters cabs by provider location"),
    lon: float = Query(default=None, description="Longitude: if provided with lat (and location not set), filters cabs by provider location"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers (used with location/lat/lon)"),
    min_capacity: int = Query(default=None, ge=1, description="Minimum passenger capacity filter"),
    max_capacity: int = Query(default=None, ge=1, description="Maximum passenger capacity filter"),
    min_minimum_rate: int = Query(default=None, ge=0, description="Minimum minimum rate filter"),
    max_minimum_rate: int = Query(default=None, ge=0, description="Maximum minimum rate filter"),
    min_per_km_rate: int = Query(default=None, ge=0, description="Minimum per km rate filter"),
    max_per_km_rate: int = Query(default=None, ge=0, description="Maximum per km rate filter"),
    min_km_for_minimum_rate: int = Query(default=None, ge=0, description="Minimum km for minimum rate filter"),
    max_km_for_minimum_rate: int = Query(default=None, ge=0, description="Maximum km for minimum rate filter"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Query cabs with optional vehicle type, location-based provider filtering, and capacity/rate filters.
    
    **Authorization**: Public (no authentication required).
    
    **Location-Based Search**:
    - `location`: Place name (e.g., "Bangalore", "New York"). If provided, lat/lon are ignored.
      - Automatically resolved to coordinates via geocoding
      - Cached for performance
    - `lat` + `lon`: Direct coordinates. Used if `location` not provided.
    - `radius_km`: Search radius in kilometers (default 5km)
    
    **Filtering Logic** (all optional):
    - `provider_id`: Filter to a specific provider's cabs
    - `vehicle_type`: Filter by vehicle type string (e.g., SEDAN, SUV, HATCHBACK, etc.)
    - `min_capacity` / `max_capacity`: Filter by passenger capacity (inclusive bounds)
    - `min_minimum_rate` / `max_minimum_rate`: Filter by minimum rate (inclusive bounds)
    - `min_per_km_rate` / `max_per_km_rate`: Filter by per km rate (inclusive bounds)
    - `min_km_for_minimum_rate` / `max_km_for_minimum_rate`: Filter by km for minimum rate (inclusive bounds)
    
    **Location-Based Search Note**: 
    This is a provider-level filter using provider location, not individual cab location.
    The bbox algorithm is fast but approximate (±0.1° accuracy per 11km).
    
    **Response**: `{ data: List[CabPublic], count: int }`
    """
    # Resolve location to coordinates if provided
    if location:
        coords = await resolve_location(location, session)
        if not coords:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve location '{location}'. Please try a different place name.",
            )
        lat, lon = coords
    
    provider_ids = None
    if lat is not None and lon is not None:
        # Get provider IDs within the bounding box around the coordinates
        provider_ids = crud._providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    results, count = crud.list_cabs_query(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        provider_ids=provider_ids,
        vehicle_type=vehicle_type,
        min_capacity=min_capacity,
        max_capacity=max_capacity,
        min_minimum_rate=min_minimum_rate,
        max_minimum_rate=max_minimum_rate,
        min_per_km_rate=min_per_km_rate,
        max_per_km_rate=max_per_km_rate,
        min_km_for_minimum_rate=min_km_for_minimum_rate,
        max_km_for_minimum_rate=max_km_for_minimum_rate,
        limit=limit,
        offset=offset,
    )
    return {"data": results, "count": count}


@router.get("/drivers", response_model=DriversList)
async def query_drivers(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None, description="Filter by specific driver provider"),
    location: str = Query(default=None, description="Place name to search near (e.g., 'Bangalore', 'New York'). If provided, lat/lon are ignored."),
    lat: float = Query(default=None, description="Latitude: if provided with lon (and location not set), filters drivers by provider location"),
    lon: float = Query(default=None, description="Longitude: if provided with lat (and location not set), filters drivers by provider location"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers (used with location/lat/lon)"),
    min_capacity: int = Query(default=None, ge=1, description="Minimum capacity of associated cabs filter"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Query drivers with optional location-based provider filtering and capacity filtering.
    
    **Authorization**: Public (no authentication required).
    
    **Location-Based Search**:
    - `location`: Place name (e.g., "Bangalore", "New York"). If provided, lat/lon are ignored.
      - Automatically resolved to coordinates
      - Cached for performance
    - `lat` + `lon`: Direct coordinates. Used if `location` not provided.
    - `radius_km`: Search radius in kilometers (default 5km)
    
    **Filtering Logic**:
    - `provider_id`: Filter to a specific provider's drivers
    - `min_capacity`: Filter drivers who have at least one cab with capacity >= min_capacity
    
    **Response**: `{ data: List[DriverPublic], count: int }`
    - Each driver object includes flattened profile/contact fields such as full_name, primary_phone_number, primary_email, and other profile details.
    """
    # Resolve location to coordinates if provided
    if location:
        coords = await resolve_location(location, session)
        if not coords:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve location '{location}'. Please try a different place name.",
            )
        lat, lon = coords
    
    provider_ids = None
    if lat is not None and lon is not None:
        # Get provider IDs within the bounding box around the coordinates
        provider_ids = crud._providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    results, count = crud.list_drivers_query(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        provider_ids=provider_ids,
        min_capacity=min_capacity,
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


@router.get("/stay-providers-near-location", response_model=PublicStayProviderList)
async def query_stay_providers_near_location(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    location: str = Query(..., description="Place name to search near (e.g., 'Bangalore', 'New York'). Will be resolved to coordinates."),
    radius_km: float = Query(default=10.0, ge=0.1, description="Search radius in kilometers"),
    min_price: int = Query(default=None, ge=0, description="Minimum room rate filter"),
    max_price: int = Query(default=None, ge=0, description="Maximum room rate filter"),
    pax_count: int = Query(default=None, ge=1, description="Minimum occupancy required"),
    room_count: int = Query(default=None, ge=1, description="Minimum number of rooms required"),
    amenities: List[str] = Query(default=None, description="List of required amenities (AND semantics)"),
    sort_by_distance: bool = Query(default=False, description="If True, sort results by distance from location"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
) -> dict:
    """
    Find stay providers near a place name with optional filters and distance sorting.

    **Authorization**: superuser or agency staff only.

    **Location Resolution**:
    - Accepts human-readable place names (e.g., "Bangalore", "Times Square", "Kochi")
    - Automatically resolves to coordinates via OpenStreetMap Nominatim API
    - Results cached in LocationLookup table for fast repeated lookups
    - In-memory cache with 24-hour TTL

    **Geographic Search**:
    - `location`: Required. Place name to search near
    - `radius_km`: Search radius in kilometers (default 10km)
    - Uses provider location as the anchor
    - Returns providers within the specified radius

    **Filtering Logic** (all optional, combined with AND):
    - `min_price` / `max_price`: Filter providers by unit room_rate
    - `pax_count`: Filter providers with units accommodating guests
    - `room_count`: Filter providers with at least this many rooms
    - `amenities`: AND semantics - units must have ALL listed amenities

    **Sorting**:
    - If `sort_by_distance=True`: Results sorted by distance from resolved location (nearest first)
    - If False: Results in database order

    **Pagination**: Use `limit` and `offset` together.

    **Response**: Returns `{ data: List[StayProviderPublic], count: int }`

    **Error Handling**:
    - If location cannot be resolved: Returns 400 Bad Request
    - If no providers found: Returns empty list with count=0

    **Example Queries**:
    ```
    GET /query/stay-providers-near-location?location=Bangalore&radius_km=15&min_price=100&max_price=500
    GET /query/stay-providers-near-location?location=Kochi&amenities=wifi&amenities=pool&sort_by_distance=true
    ```
    """
    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay providers")

    # Resolve location name to coordinates
    coords = await resolve_location(location, session)
    if not coords:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve location '{location}'. Please try a different place name.",
        )

    lat, lon = coords

    # Normalize amenities
    if amenities and len(amenities) == 1 and "," in amenities[0]:
        amenities = amenities[0].split(",")
    if amenities:
        normalized = []
        for amenity in amenities:
            candidate = amenity.strip()
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        amenities = normalized or None

    # Query providers
    providers, count = crud.list_stay_providers_by_location(
        session=session,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        min_price=min_price,
        max_price=max_price,
        pax_count=pax_count,
        room_count=room_count,
        amenities=amenities,
        limit=limit,
        offset=offset,
        sort_by_distance=sort_by_distance,
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


@router.get("/cabs-near-location", response_model=CabsList)
async def query_cabs_near_location(
    *,
    session: SessionDep,
    location: str = Query(..., description="Place name to search near (e.g., 'Bangalore', 'New York')"),
    radius_km: float = Query(default=5.0, ge=0.1, description="Search radius in kilometers"),
    vehicle_type: VehicleType = Query(default=None, description="Filter by vehicle type"),
    min_capacity: int = Query(default=None, ge=1, description="Minimum passenger capacity"),
    max_capacity: int = Query(default=None, ge=1, description="Maximum passenger capacity"),
    sort_by_distance: bool = Query(default=False, description="If True, sort by distance from location"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Results to skip (pagination)"),
):
    """
    Find cabs near a place name with optional filters and distance sorting.

    **Authorization**: Public (no authentication required).

    **Location Resolution**:
    - Accepts human-readable place names (e.g., "Bangalore", "Times Square")
    - Automatically resolves to coordinates
    - Cached for performance with 24-hour TTL

    **Geographic Search**:
    - `location`: Required. Place name to search near
    - `radius_km`: Search radius in kilometers (default 5km)
    - Returns cabs from providers within the radius

    **Filtering Logic** (all optional):
    - `vehicle_type`: Filter by vehicle type (e.g., SEDAN, SUV, HATCHBACK)
    - `min_capacity` / `max_capacity`: Filter by passenger capacity (inclusive)

    **Sorting**:
    - If `sort_by_distance=True`: Results sorted by distance (nearest first)

    **Response**: `{ data: List[CabPublic], count: int }`

    **Example**:
    ```
    GET /query/cabs-near-location?location=bangalore&radius_km=10&min_capacity=4&sort_by_distance=true
    ```
    """
    # Resolve location name to coordinates
    coords = await resolve_location(location, session)
    if not coords:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve location '{location}'. Please try a different place name.",
        )

    lat, lon = coords

    # Query cabs
    results, count = crud.list_cabs_by_location(
        session=session,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        vehicle_type=vehicle_type,
        min_capacity=min_capacity,
        max_capacity=max_capacity,
        limit=limit,
        offset=offset,
        sort_by_distance=sort_by_distance,
    )

    return {"data": results, "count": count}


__all__ = ["router"]
