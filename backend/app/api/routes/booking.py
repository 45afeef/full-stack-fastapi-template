
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, Session

from app.api.deps import SessionDep, get_current_user, CurrentUser
from app.api.routes.agency import _is_agency_owner
from app.models.travel.booking import Booking, BookingTraveller, BookingCab, BookingStay
from app.models.travel.providers import TravelAgencyStaff, TravelAgency, CabServiceProvider, StayServiceProvider
from app.models.travel.cab import Cab
from app.models.travel.stay import StayUnit
from app.models.user.profile import Profile
from app.schemas.travel.booking import BookingCreate, BookingUpdate


router = APIRouter(prefix="/booking", tags=["booking"])


def _get_staff_records(session: Session, user_id: uuid.UUID) -> list[TravelAgencyStaff]:
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.user_id == user_id)
    return session.exec(statement).all()


@router.post("/", dependencies=[Depends(get_current_user)], response_model=Booking)
def create_booking(session: SessionDep, booking_in: BookingCreate, current_user: CurrentUser) -> Any:
    """Create a booking. Only agency staff may create bookings. This operation creates Booking and related
    BookingTraveller/BookingCab/BookingStay rows transactionally.
    """
    # require staff
    staff_records = _get_staff_records(session, current_user.id)
    if not staff_records and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only agency staff can create bookings")

    # Determine travel_agency and staff id to attach
    staff_rec = None
    if staff_records:
        # prefer a staff record that matches provided agency if provided
        if booking_in.travel_agency_id:
            for s in staff_records:
                if str(s.travel_agency_id) == str(booking_in.travel_agency_id):
                    staff_rec = s
                    break
        # otherwise take the first staff record
        if not staff_rec:
            staff_rec = staff_records[0]

    # do not set attributes on the input model (it's a pydantic/SQLModel instance);
    # we'll inject these into the payload dict below when creating the Booking

    # prepare booking data (exclude nested lists)
    payload = booking_in.model_dump(exclude_unset=True)
    travellers = payload.pop("travellers", None) or []
    cabs = payload.pop("cabs", None) or []
    stays = payload.pop("stays", None) or []

    # attach staff agency fields if available
    if staff_rec:
        payload["travel_agency_id"] = str(staff_rec.travel_agency_id)
        payload["travel_agency_staff_id"] = str(staff_rec.id)

    # ensure booking id
    if "id" not in payload or not payload.get("id"):
        payload["id"] = uuid.uuid4()

    # create in-session (avoid starting a nested transaction; the session may already be transactional in tests)
    try:
        booking_obj = Booking(**payload)
        session.add(booking_obj)
        # flush to populate booking_obj.id for FK references
        session.flush()

        # create traveller links
        for t in travellers:
            # ensure traveller profile exists
            traveller_id = t["traveller_id"] if isinstance(t, dict) else t.traveller_id
            p = session.get(Profile, traveller_id)
            if not p:
                session.rollback()
                raise HTTPException(status_code=404, detail=f"Traveller profile {traveller_id} not found")
            bt = BookingTraveller(id=uuid.uuid4(), booking_id=booking_obj.id, traveller_id=traveller_id)
            session.add(bt)

        # create cab links
        for c in cabs:
            cab_id = c["cab_id"] if isinstance(c, dict) else c.cab_id
            cab_obj = session.get(Cab, cab_id)
            if not cab_obj:
                session.rollback()
                raise HTTPException(status_code=404, detail=f"Cab {cab_id} not found")
            bc = BookingCab(
                id=uuid.uuid4(),
                booking_id=booking_obj.id,
                cab_id=cab_id,
                cab_provider_id=(c.get("cab_provider_id") if isinstance(c, dict) else c.cab_provider_id),
                pickup_time=(c.get("pickup_time") if isinstance(c, dict) else c.pickup_time),
                pickup_location=(c.get("pickup_location") if isinstance(c, dict) else c.pickup_location),
                drop_time=(c.get("drop_time") if isinstance(c, dict) else c.drop_time),
                drop_location=(c.get("drop_location") if isinstance(c, dict) else c.drop_location),
                driver_id=(c.get("driver_id") if isinstance(c, dict) else c.driver_id),
                rate=(c.get("rate") if isinstance(c, dict) else c.rate),
                status=(c.get("status") if isinstance(c, dict) else c.status),
                notes=(c.get("notes") if isinstance(c, dict) else c.notes),
            )
            session.add(bc)

        # create stay links
        for s in stays:
            stayunit_id = s["stayunit_id"] if isinstance(s, dict) else s.stayunit_id
            stayunit = session.get(StayUnit, stayunit_id)
            if not stayunit:
                session.rollback()
                raise HTTPException(status_code=404, detail=f"Stay unit {stayunit_id} not found")
            bs = BookingStay(
                id=uuid.uuid4(),
                booking_id=booking_obj.id,
                stayunit_id=stayunit_id,
                stay_provider_id=(s.get("stay_provider_id") if isinstance(s, dict) else s.stay_provider_id),
                check_in=(s.get("check_in") if isinstance(s, dict) else s.check_in),
                check_out=(s.get("check_out") if isinstance(s, dict) else s.check_out),
                room_type=(s.get("room_type") if isinstance(s, dict) else s.room_type),
                rate=(s.get("rate") if isinstance(s, dict) else s.rate),
                status=(s.get("status") if isinstance(s, dict) else s.status),
            )
            session.add(bs)

        # commit once everything is added
        session.commit()
    except HTTPException:
        # already rolled back where appropriate; re-raise
        raise
    except Exception:
        session.rollback()
        raise

    # refresh and return
    session.refresh(booking_obj)
    return booking_obj


@router.get("/", dependencies=[Depends(get_current_user)], response_model=list[Booking])
def list_bookings(session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> Any:
    """List bookings with permission rules:
    - superuser: all
    - agency owner: all bookings for agencies they own
    - agency staff: only bookings created by that staff user (travel_agency_staff_id)
    """
    # superuser: return all
    if current_user.is_superuser:
        stmt = select(Booking).offset(skip).limit(limit)
        return session.exec(stmt).all()

    # check if agency owner for any agency
    # find agencies owned by user
    statement = select(TravelAgency).where(TravelAgency.created_by == current_user.id)
    owned_agencies = session.exec(statement).all()
    if owned_agencies:
        agency_ids = [a.id for a in owned_agencies]
        stmt = select(Booking).where(Booking.travel_agency_id.in_(agency_ids)).offset(skip).limit(limit)
        return session.exec(stmt).all()

    # otherwise must be staff and only see own bookings
    staff_records = _get_staff_records(session, current_user.id)
    if not staff_records:
        raise HTTPException(status_code=403, detail="Not authorized to list bookings")
    staff_ids = [s.id for s in staff_records]
    stmt = select(Booking).where(Booking.travel_agency_staff_id.in_(staff_ids)).offset(skip).limit(limit)
    return session.exec(stmt).all()


@router.get("/{booking_id}", dependencies=[Depends(get_current_user)], response_model=Booking)
def get_booking(booking_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Fetch a single booking according to permission rules."""
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if current_user.is_superuser:
        return booking

    # agency owner?
    agency = None
    if booking.travel_agency_id:
        agency = session.get(TravelAgency, booking.travel_agency_id)
    if agency and _is_agency_owner(session, current_user, agency):
        return booking

    # agency staff: must be creator (travel_agency_staff_id)
    staff_records = _get_staff_records(session, current_user.id)
    staff_ids = {s.id for s in staff_records}
    if booking.travel_agency_staff_id and booking.travel_agency_staff_id in staff_ids:
        return booking

    raise HTTPException(status_code=403, detail="Not authorized to view this booking")


@router.patch("/{booking_id}", dependencies=[Depends(get_current_user)], response_model=Booking)
def update_booking(booking_id: uuid.UUID, booking_in: BookingUpdate, session: SessionDep, current_user: CurrentUser) -> Any:
    """Update booking. Staff can update only their own bookings; superuser allowed to update any."""
    booking = session.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if not current_user.is_superuser:
        # must be staff and owner of booking
        staff_records = _get_staff_records(session, current_user.id)
        if not staff_records:
            raise HTTPException(status_code=403, detail="Not authorized to update booking")
        staff_ids = {s.id for s in staff_records}
        if booking.travel_agency_staff_id not in staff_ids:
            raise HTTPException(status_code=403, detail="Not authorized to update this booking")

    update_data = booking_in.model_dump(exclude_unset=True)
    # disallow changing ownership fields
    for k in ("id", "travel_agency_id", "travel_agency_staff_id"):
        update_data.pop(k, None)

    booking.sqlmodel_update(update_data)
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


__all__ = ["router"]
