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


@router.post("/agencies", response_model=AgencyPublic, dependencies=[Depends(get_current_active_superuser)])
def create_agency(*, session: SessionDep, agency: AgencyCreate) -> Any:
    # Found a bug - 500 error when suppling user id not existing in User table
    user = session.get(User, agency.created_by)
    if not user:
        raise HTTPException(status_code=404, detail="User not found for created_by")

    agency_obj = crud.create_travel_agency(session=session, agency=agency.model_dump())
    return agency_obj


@router.post("/agencies/{agency_id}/staffs", dependencies=[Depends(get_current_active_superuser)])
def assign_agency_staff(*, agency_id: uuid.UUID, session: SessionDep, staff: AgencyStaffCreate) -> Any:
    # ensure agency exists
    from app.models.travel.providers import TravelAgency

    agency = session.get(TravelAgency, agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    staff_data = staff.model_dump()
    from app.models.travel.providers import TravelAgencyStaff as TAS

    staff_obj = TAS(**staff_data, travel_agency_id=agency_id)
    created = crud.assign_agency_staff(session=session, staff=staff_obj)
    return created


def _is_agency_staff(session: Session, user: User) -> bool:
    from sqlmodel import select
    from app.models.travel.providers import TravelAgencyStaff

    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.user_id == user.id)
    found = session.exec(statement).first()
    return found is not None


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
    if not current_user.is_superuser and not _is_agency_staff(session, current_user):
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
