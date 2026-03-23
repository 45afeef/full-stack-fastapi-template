import uuid
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import SessionDep, CurrentUser, get_current_active_superuser, get_current_user
from app import crud
from app.models import User
from app.models.travel.providers import ServiceProvider
from app.models.travel.stay import StayUnit, StayAmenity
from app.schemas.provider.stays import (
    StayUnitCreate,
    StayUnitPublic,
    UnitsList,
    StayAmenityCreate,
    StayAmenityPublic,
    StayAmenitiesList,
)

router = APIRouter(prefix="/{provider_id}/stay", tags=["providers-stay"])


def _is_provider_owner(session: Session, user: User, provider: ServiceProvider) -> bool:
    return provider.owner_id == user.id


@router.post("/units", response_model=StayUnitPublic, dependencies=[Depends(get_current_active_superuser)])
def create_stay_unit(*, provider_id: uuid.UUID, session: SessionDep, unit: StayUnitCreate,) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    unit_obj = StayUnit(**unit.model_dump(), provider_id=provider_id)
    created = crud.create_stay_unit(session=session, unit=unit_obj)
    return created


@router.post("/units/{unit_id}/amenities", response_model=StayAmenityPublic, dependencies=[Depends(get_current_active_superuser)])
def add_amenity(*, provider_id: uuid.UUID, unit_id: uuid.UUID, session: SessionDep, amenity: StayAmenityCreate,) -> Any:
    # create a new amenity attached to the given stay unit
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    # verify that the unit exists and belongs to this provider
    unit = session.get(StayUnit, unit_id)
    if not unit or unit.provider_id != provider_id:
        raise HTTPException(status_code=404, detail="Stay unit not found")
    amenity_obj = StayAmenity(**amenity.model_dump(), stay_service_provider_id=provider_id, stay_unit_id=unit_id)
    created = crud.create_stay_amenity(session=session, amenity=amenity_obj)
    return created


@router.get("/units", response_model=UnitsList, dependencies=[Depends(get_current_user)])
def list_stay_units(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    provider_id: uuid.UUID,
    min_price: int = Query(default=0),
    max_price: int = Query(default=None),
    amenities: List[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    # allow superuser and agency staff (agency staff check reused from agency module)
    from app.api.routes.agency import is_agency_staff

    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay units")

    units, count = crud.list_stay_units(
        session=session,
        provider_id=str(provider_id),
        min_price=min_price,
        max_price=max_price,
        amenities=amenities,
        limit=limit,
        offset=offset,
    )
    return UnitsList(data=units, count=count)




@router.get(
    "/units/{unit_id}/amenities",
    response_model=StayAmenitiesList,
)
def list_amenities(*, provider_id: uuid.UUID, unit_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not (current_user.is_superuser or _is_provider_owner(session, current_user, provider)):
        raise HTTPException(status_code=403, detail="Not authorized to list amenities")
    amenities = crud.list_stay_amenities(
        session=session, provider_id=str(provider_id), unit_id=str(unit_id)
    )
    return StayAmenitiesList(data=amenities, count=len(amenities))


__all__ = ["router"]
