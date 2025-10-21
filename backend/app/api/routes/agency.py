import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import SessionDep, get_current_active_superuser
from app import crud
from app.models import User
from app.models.travel.providers import TravelAgency, TravelAgencyStaff
from app.schemas.stays import AgencyCreate, AgencyPublic, AgencyStaffCreate

router = APIRouter(prefix="/travel-agency", tags=["agencies"]) 


@router.post("", response_model=AgencyPublic, dependencies=[Depends(get_current_active_superuser)])
def create_agency(*, session: SessionDep, agency: AgencyCreate) -> Any:
    """Admin: create a travel agency."""
    user = session.get(User, agency.created_by)
    if not user:
        raise HTTPException(status_code=404, detail="User not found for created_by")

    agency_obj = crud.create_travel_agency(session=session, agency=agency.model_dump())
    return agency_obj


@router.post("/{agency_id}/staffs", dependencies=[Depends(get_current_active_superuser)])
def assign_agency_staff(*, agency_id: uuid.UUID, session: SessionDep, staff: AgencyStaffCreate) -> Any:
    """Admin: assign a user as staff to an existing travel agency."""
    agency = session.get(TravelAgency, agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    staff_data = staff.model_dump()
    staff_obj = TravelAgencyStaff(**staff_data, travel_agency_id=agency_id)
    created = crud.assign_agency_staff(session=session, staff=staff_obj)
    return created


def is_agency_staff(session: Session, user: User) -> bool:
    """Helper: return True if the user is registered as agency staff."""
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.user_id == user.id)
    found = session.exec(statement).first()
    return found is not None


__all__ = ["router", "is_agency_staff"]
