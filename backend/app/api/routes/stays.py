import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app import crud
from app.models import User
from app.models.travel.stay import StayUnit
from app.models.travel.providers import ServiceProvider
from app.schemas.stays import (
    ProviderCreate,
    ProviderPublic,
    StayUnitCreate,
    StayUnitPublic,
    AgencyCreate,
    AgencyPublic,
    AgencyStaffCreate,
    UnitFilterParams,
    UnitsList,
)
from app.api.routes.agency import is_agency_staff

router = APIRouter(prefix="/stays", tags=["stays"])


@router.post("/providers", response_model=ProviderPublic, dependencies=[Depends(get_current_active_superuser)])
def create_stay_provider(*, session: SessionDep, provider: ProviderCreate) -> Any:
    """Admin: create a service provider and a stay-specific provider record."""
    provider_data = provider.model_dump()
    sp = ServiceProvider(**provider_data)
    created = crud.create_service_provider(session=session, provider=sp)
    # create stay-specific row
    crud.create_stay_provider_row(session=session, provider_id=created.id)
    return created


@router.post("/providers/{provider_id}/units", response_model=StayUnitPublic, dependencies=[Depends(get_current_active_superuser)])
def create_stay_unit(*, provider_id: uuid.UUID, session: SessionDep, unit: StayUnitCreate) -> Any:
    """Admin: create a stay unit for a provider."""
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    unit_data = unit.model_dump()
    unit_obj = StayUnit(**unit_data, provider_id=provider_id)
    created = crud.create_stay_unit(session=session, unit=unit_obj)
    return created





@router.get("/units", response_model=UnitsList)
def list_stay_units(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    provider_id: uuid.UUID | None = Query(default=None),
    min_price: int | None = Query(default=None),
    max_price: int | None = Query(default=None),
    amenity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """Agency staff: list available stay units with filtering and pagination."""
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
