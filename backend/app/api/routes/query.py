import uuid
from typing import Any, List

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app import crud
from app.schemas.provider.stays import (
    UnitsList,
)
from app.schemas.provider.cab import CabPublic, DriverPublic
from app.schemas.provider.cab import CabPublic as CabSchema
from app.schemas.provider.stays import StayUnitPublic
from app.api.routes.agency import is_agency_staff
from app.models.travel.enums import VehicleType

router = APIRouter(prefix="/query", tags=["query"])


# This endpoint supports both the following ways of amenity url params
# GET /units?min_price=1000&max_price=5000&amenities=wifi&amenities=ac
# GET /units?amenities=wifi,pool
@router.get("/units", response_model=UnitsList)
def list_stay_units(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    provider_id: uuid.UUID = Query(default=None),
    min_price: int = Query(default=None),
    max_price: int = Query(default=None),
    amenities: List[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Agency staff: list available stay units with filtering and pagination."""
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
        amenities=amenities,
        limit=limit,
        offset=offset,
    )
    return UnitsList(data=units, count=count)


@router.get("/cabs", response_model=dict)
def query_cabs(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None),
    vehicle_type: VehicleType = Query(default=None),
    lat: float = Query(default=None),
    lon: float = Query(default=None),
    radius_km: float = Query(default=5.0, ge=0.1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Query cabs with optional vehicle type and location-based provider filtering.

    Returns an object { data: List[CabPublic], count: int }
    """
    provider_ids = None
    if lat is not None and lon is not None:
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


@router.get("/drivers", response_model=dict)
def query_drivers(
    *,
    session: SessionDep,
    provider_id: uuid.UUID = Query(default=None),
    lat: float = Query(default=None),
    lon: float = Query(default=None),
    radius_km: float = Query(default=5.0, ge=0.1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Query drivers with optional location-based provider filtering."""
    provider_ids = None
    if lat is not None and lon is not None:
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
    lat: float = Query(..., description="Latitude to search near"),
    lon: float = Query(..., description="Longitude to search near"),
    radius_km: float = Query(default=5.0, ge=0.1),
    amenity: str = Query(default=None),
    min_price: int = Query(default=None),
    max_price: int = Query(default=None),
    sort_by_distance: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Driver/agencies: find stay units near a point with optional filters.

    Permission: allow superusers and agency staff (same as listing stay units).
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
