import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import SessionDep, get_current_active_superuser, get_current_user, CurrentUser
from app import crud
from app.models import User
from app.models.travel.providers import TravelAgency, TravelAgencyStaff
from app.schemas.stays import (
    AgencyCreate,
    AgencyPublic,
    AgencyStaffCreate,
    AgencyDetail,
    AgencyUpdate,
    AgencyStaffPublic,
    AgencyStaffUpdate,
)

router = APIRouter(prefix="/travel-agency", tags=["agencies"]) 


def _is_agency_owner(session: Session, user: User, agency: TravelAgency) -> bool:
    return agency.created_by == user.id


@router.post("", response_model=AgencyPublic, dependencies=[Depends(get_current_active_superuser)])
def create_agency(*, session: SessionDep, agency: AgencyCreate) -> Any:
    """Superuser: create a travel agency."""
    user = session.get(User, agency.created_by)
    if not user:
        raise HTTPException(status_code=404, detail="User not found for created_by")

    agency_obj = crud.create_travel_agency(session=session, agency=agency.model_dump())
    return agency_obj


@router.get("", response_model=list[AgencyPublic], dependencies=[Depends(get_current_active_superuser)])
def list_agencies(*, session: SessionDep) -> Any:
    """Superuser: list agencies."""
    return crud.list_travel_agencies(session=session)


@router.get("/{agency_id}", response_model=AgencyDetail)
def get_agency(*, agency_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Get agency detail. Superuser or owner or staff can view details."""
    agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    # allow superuser, owner, or any staff
    if current_user.is_superuser:
        return agency
    if _is_agency_owner(session, current_user, agency):
        return agency
    # check staff membership
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.travel_agency_id == agency.id).where(TravelAgencyStaff.user_id == current_user.id)
    found = session.exec(statement).first()
    if found:
        return agency
    raise HTTPException(status_code=403, detail="Not authorized to view agency")


@router.put("/{agency_id}", response_model=AgencyPublic)
def update_agency(*, agency_id: uuid.UUID, session: SessionDep, agency_in: AgencyUpdate, current_user: CurrentUser) -> Any:
    """Superuser can update any agency; owner can update their agency."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    if not (current_user.is_superuser or _is_agency_owner(session, current_user, db_agency)):
        raise HTTPException(status_code=403, detail="Not authorized to update agency")
    updated = crud.update_travel_agency(session=session, db_agency=db_agency, agency_in=agency_in.model_dump(exclude_unset=True))
    return updated


@router.delete("/{agency_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_agency(*, agency_id: uuid.UUID, session: SessionDep) -> Any:
    """Superuser: delete agency."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    crud.delete_travel_agency(session=session, db_agency=db_agency)
    return {"ok": True}


@router.post("/{agency_id}/staffs", response_model=AgencyStaffPublic)
def create_agency_staff(*, agency_id: uuid.UUID, session: SessionDep, staff: AgencyStaffCreate, current_user: CurrentUser) -> Any:
    """Agency owner or superuser can assign staff. Owner allowed; superuser allowed."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    if not (current_user.is_superuser or _is_agency_owner(session, current_user, db_agency)):
        raise HTTPException(status_code=403, detail="Not authorized to assign staff")
    # create staff record
    staff_obj = TravelAgencyStaff(**staff.model_dump(), travel_agency_id=agency_id)
    created = crud.assign_agency_staff(session=session, staff=staff_obj)
    return created


@router.get("/{agency_id}/staffs", response_model=list[AgencyStaffPublic])
def list_agency_staffs(*, agency_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Superuser, owner, or agency staff can list staff."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    # allow superuser
    if current_user.is_superuser or _is_agency_owner(session, current_user, db_agency):
        statement = select(TravelAgencyStaff).where(TravelAgencyStaff.travel_agency_id == agency_id)
        return session.exec(statement).all()
    # check if requestor is staff
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.travel_agency_id == agency_id).where(TravelAgencyStaff.user_id == current_user.id)
    found = session.exec(statement).first()
    if found:
        statement = select(TravelAgencyStaff).where(TravelAgencyStaff.travel_agency_id == agency_id)
        return session.exec(statement).all()
    raise HTTPException(status_code=403, detail="Not authorized to list staff")


@router.patch("/{agency_id}/staffs/{staff_id}", response_model=AgencyStaffPublic)
def update_agency_staff(*, agency_id: uuid.UUID, staff_id: uuid.UUID, session: SessionDep, staff_in: AgencyStaffUpdate, current_user: CurrentUser) -> Any:
    """Only agency owner or superuser can update staff role/info."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    db_staff = crud.get_agency_staff(session=session, staff_id=str(staff_id))
    if not db_staff or str(db_staff.travel_agency_id) != str(agency_id):
        raise HTTPException(status_code=404, detail="Staff not found")
    if not (current_user.is_superuser or _is_agency_owner(session, current_user, db_agency)):
        raise HTTPException(status_code=403, detail="Not authorized to update staff")
    updated = crud.update_agency_staff(session=session, db_staff=db_staff, staff_in=staff_in.model_dump(exclude_unset=True))
    return updated


@router.delete("/{agency_id}/staffs/{staff_id}")
def delete_agency_staff(*, agency_id: uuid.UUID, staff_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Only agency owner or superuser can remove staff."""
    db_agency = crud.get_travel_agency(session=session, agency_id=str(agency_id))
    if not db_agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    db_staff = crud.get_agency_staff(session=session, staff_id=str(staff_id))
    if not db_staff or str(db_staff.travel_agency_id) != str(agency_id):
        raise HTTPException(status_code=404, detail="Staff not found")
    if not (current_user.is_superuser or _is_agency_owner(session, current_user, db_agency)):
        raise HTTPException(status_code=403, detail="Not authorized to remove staff")
    crud.remove_agency_staff(session=session, db_staff=db_staff)
    return {"ok": True}


def is_agency_staff(session: Session, user: User) -> bool:
    """Helper: return True if the user is registered as agency staff."""
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.user_id == user.id)
    found = session.exec(statement).first()
    return found is not None


__all__ = ["router", "is_agency_staff"]
