import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.deps import SessionDep, CurrentUser, get_current_active_superuser, get_current_user
from app import crud
from app.models import User
from app.models.travel.providers import ServiceProvider, StayServiceProvider
from app.models.travel.stay import StayUnit, StayAmenity
from app.schemas.provider.stays import StayUnitCreate, StayUnitPublic, UnitsList

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


@router.post("/units/{unit_id}/amenities", response_model=StayAmenity, dependencies=[Depends(get_current_active_superuser)])
def add_amenity(*, provider_id: uuid.UUID, unit_id: uuid.UUID, session: SessionDep, amenity: dict,) -> Any:
    # simple amenity creation
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    amenity_obj = StayAmenity(**amenity, stay_service_provider_id=provider_id, stay_unit_id=unit_id)
    session.add(amenity_obj)
    session.commit()
    session.refresh(amenity_obj)
    return amenity_obj


@router.get("/units", response_model=UnitsList, dependencies=[Depends(get_current_user)])
def list_stay_units(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    provider_id: uuid.UUID,
    min_price: int | None = Query(default=None),
    max_price: int | None = Query(default=None),
    amenity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    # allow superuser and agency staff (agency staff check reused from agency module)
    from app.api.routes.agency import is_agency_staff

    if not current_user.is_superuser and not is_agency_staff(session, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to query stay units")

    units, count = crud.list_stay_units(
        session=session,
        provider_id=str(provider_id) if provider_id else None,
        min_price=min_price,
        max_price=max_price,
        amenity=amenity,
        limit=limit,
        offset=offset,
    )
    return UnitsList(data=units, count=count)


__all__ = ["router"]
