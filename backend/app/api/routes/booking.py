
import uuid
from typing import Any


from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, Session
from sqlalchemy.orm import selectinload, load_only

from app.booking_crud import booking_details_loader, serialize_booking
from app.api.deps import SessionDep, get_current_user, CurrentUser
from app.api.routes.agency import _is_agency_owner
from app.models.travel.booking import Booking, BookingTraveller, BookingCab, BookingStay
from app.models.travel.providers import TravelAgencyStaff, TravelAgency, CabServiceProvider
from app.models.travel.cab import Cab, Driver
from app.models.travel.stay import StayUnit
from app.models.user.profile import Profile
from app.schemas.travel.booking import BookingCreate, BookingResponse, BookingTravellerCreate, BookingUpdate, BookingRead


router = APIRouter(prefix="/booking", tags=["booking"])


def _get_staff_records(session: Session, user_id: uuid.UUID) -> list[TravelAgencyStaff]:
    statement = select(TravelAgencyStaff).where(TravelAgencyStaff.user_id == user_id)
    return session.exec(statement).all()


def _get_or_create_profile(
    session: Session,
    traveller: BookingTravellerCreate,
) -> Profile:

    if traveller.traveller_id:
        profile = session.get(Profile, traveller.traveller_id)

        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Traveller profile {traveller.traveller_id} not found",
            )

        return profile

    profile = Profile(
        name=traveller.traveller_name,
        phone=traveller.traveller_phone,
    )

    session.add(profile)
    session.flush()

    return profile



@router.post("/", dependencies=[Depends(get_current_user)], response_model=BookingRead)
def create_booking(session: SessionDep, booking_in: BookingCreate, current_user: CurrentUser) -> Any:
    """
    Create a booking and all related records transactionally. Only agency staff may create bookings. This operation creates Booking and related
    BookingTraveller/BookingCab/BookingStay rows transactionally. Returns complete booking with all nested data.

    **Authorization**: Only agency staff can create bookings. The booking will be associated with the staff user's agency and staff record.

    """

    # Verify Authorization:
    # Verifiy the user is staff for at least one agency (unless superuser) - we need this to determine which agency to attach the booking to and to enforce permissions. We require staff status to create a booking because we need to associate the booking with an agency, and only staff are associated with agencies.
    # require staff


    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------
    staff_records = _get_staff_records(session, current_user.id)

    if not staff_records and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only agency staff can create bookings")

    staff_rec = None

    if staff_records:
        if booking_in.travel_agency_id:
            staff_rec = next(
                (
                    staff
                    for staff in staff_records
                    if staff.travel_agency_id == booking_in.travel_agency_id
                ),
                None,
            )

        staff_rec = staff_rec or staff_records[0]

    # ------------------------------------------------------------------
    # Extract nested data before creating Booking
    # ------------------------------------------------------------------
    travellers: list[BookingTravellerCreate] = booking_in.travellers or []
    cabs = booking_in.cabs or []
    stays = booking_in.stays or []

    payload = booking_in.model_dump(
        exclude={
            "travellers",
            "cabs",
            "stays",
        },
        exclude_unset=True,
    )

    if staff_rec:
        payload["travel_agency_id"] = staff_rec.travel_agency_id
        payload["travel_agency_staff_id"] = staff_rec.id

    try:
        # ------------------------------------------------------------------
        # Create booking
        # ------------------------------------------------------------------
        booking_obj = Booking(**payload)

        session.add(booking_obj)
        session.flush()

        # ------------------------------------------------------------------
        # Travellers
        # ------------------------------------------------------------------
        for traveller in travellers:

            profile = _get_or_create_profile(session,traveller)

            session.add(
                BookingTraveller(
                    booking_id=booking_obj.id,
                    traveller_id=profile.id,
                )
            )

        # ------------------------------------------------------------------
        # Cabs
        # ------------------------------------------------------------------
        for cab in cabs:

            cab_obj = session.get(Cab, cab.cab_id)

            if not cab_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"Cab {cab.cab_id} not found",
                )

            cab_provider_id = (
                cab.cab_provider_id
                or getattr(cab_obj, "cab_provider_id", None)
                or getattr(cab_obj, "provider_id", None)
            )

            if not cab_provider_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cab provider id for cab {cab.cab_id} is required",
                )

            session.add(
                BookingCab(
                    booking_id=booking_obj.id,
                    cab_id=cab.cab_id,
                    cab_provider_id=cab_provider_id,
                    pickup_time=cab.pickup_time,
                    pickup_location=cab.pickup_location,
                    drop_time=cab.drop_time,
                    drop_location=cab.drop_location,
                    driver_id=cab.driver_id,
                    rate=cab.rate,
                    status=cab.status,
                    # notes=cab.notes,
                )
            )

        # ------------------------------------------------------------------
        # Stays
        # ------------------------------------------------------------------
        for stay in stays:
            session.add(
                BookingStay(
                    booking_id=booking_obj.id,
                    stayunit_id=stay.stayunit_id,
                    stay_provider_id=stay.stay_provider_id,
                    check_in=stay.check_in,
                    check_out=stay.check_out,
                    room_type=stay.room_type,
                    rate=stay.rate,
                    status=stay.status,
                )
            )

        session.commit()

    except Exception:
        session.rollback()
        raise

    # ------------------------------------------------------------------
    # Reload with relationships
    # ------------------------------------------------------------------
    stmt = (
        select(Booking)
        .where(Booking.id == booking_obj.id)
        .options(
            selectinload(Booking.travellers).selectinload(
                BookingTraveller.traveller
            ),
            selectinload(Booking.cabs).selectinload(
                BookingCab.cab
            ),
            selectinload(Booking.cabs)
            .selectinload(BookingCab.driver)
            .selectinload(Driver.profile),
            selectinload(Booking.stays)
            .selectinload(BookingStay.stayunit)
            .selectinload(StayUnit.provider),
        )
    )

    return session.exec(stmt).first()


@router.get("/", dependencies=[Depends(get_current_user)], response_model=list[BookingResponse])
def list_bookings(session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> Any:
    """
    List bookings with all nested information (travellers, cabs, stays) with permission rules:
    - superuser: all
    - agency owner: all bookings for agencies they own
    - agency staff: only bookings created by that staff user (travel_agency_staff_id)
    """

    stmt = select(Booking)
    
    # Check Authentication
    # Superuser: return all
    # Owner: can see all booking of thier owned agencies
    # Staff: can see booking created by themself
    if current_user.is_superuser:
        pass

    else:
        owned_agencies = session.exec(
            select(TravelAgency)
            .where(TravelAgency.created_by == current_user.id)
        ).all()

        if owned_agencies:
            agency_ids = [a.id for a in owned_agencies]

            stmt = stmt.where(
                Booking.travel_agency_id.in_(agency_ids)
            )

        else:
            staff_records = _get_staff_records(
                session,
                current_user.id
            )

            if not staff_records:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized",
                )

            stmt = stmt.where(
                Booking.travel_agency_staff_id.in_(
                    [s.id for s in staff_records]
                )
            )

    stmt = (
        booking_details_loader(stmt)
        .offset(skip)
        .limit(limit)
        .order_by(Booking.booking_date.desc())
    )

    bookings = session.exec(stmt).all()

    return [
        serialize_booking(b)
        for b in bookings
    ]


@router.get("/{booking_id}", dependencies=[Depends(get_current_user)], response_model=BookingResponse)
def get_booking(booking_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    """Fetch a single booking with all nested information according to permission rules."""

    # First fetch only fields needed for authorization
    booking_meta = session.exec(
        select(
            Booking.id,
            Booking.travel_agency_id,
            Booking.travel_agency_staff_id,
        ).where(Booking.id == booking_id)
    ).first()

    if not booking_meta:
        raise HTTPException(
            # don't reveal that the booking doesn't exist vs. not authorized
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this booking",
        )

    _, travel_agency_id, travel_agency_staff_id = booking_meta

    # Superuser can access any booking
    if not current_user.is_superuser:
        authorized = False

        # Agency owner
        if travel_agency_id:
            agency = session.get(TravelAgency, travel_agency_id)
            if agency and _is_agency_owner(session, current_user, agency):
                authorized = True

        # Agency staff must be creator
        if not authorized:
            staff_records = _get_staff_records(session, current_user.id)
            staff_ids = {s.id for s in staff_records}

            if (
                travel_agency_staff_id
                and travel_agency_staff_id in staff_ids
            ):
                authorized = True

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this booking",
            )

    # Load full booking only after authorization succeeds
    stmt = booking_details_loader(
        select(Booking).where(Booking.id == booking_id)
    )

    booking = session.exec(stmt).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return serialize_booking(booking)

# item = item if isinstance(item, dict) else item.model_dump(exclude_unset=True)


@router.patch("/{booking_id}", dependencies=[Depends(get_current_user)], response_model=BookingRead)
def update_booking(booking_id: uuid.UUID, booking_in: BookingUpdate, session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Update a booking and synchronize all related records.

    ===========================================================================
    UPDATE STRATEGY
    ===========================================================================

    This endpoint uses DIFFERENTIAL SYNCHRONIZATION for nested collections.

    Booking scalar fields:
        - booking_date
        - status
        - total_amount

    are updated normally.

    Nested collections:
        - travellers
        - cabs
        - stays

    are synchronized using the following rules:

    ---------------------------------------------------------------------------
    Rule #1: Collection omitted
    ---------------------------------------------------------------------------

    Request:

        {
            "status": "confirmed"
        }

    Result:

        - booking.status updated
        - travellers unchanged
        - cabs unchanged
        - stays unchanged

    ---------------------------------------------------------------------------
    Rule #2: Existing child row (id provided)
    ---------------------------------------------------------------------------

    Request:

        {
            "cabs": [
                {
                    "id": "booking-cab-row-id",
                    "status": "confirmed"
                }
            ]
        }

    Result:

        Existing BookingCab row is updated.

    ---------------------------------------------------------------------------
    Rule #3: New child row (id omitted)
    ---------------------------------------------------------------------------

    Request:

        {
            "cabs": [
                {
                    "cab_id": "cab-id",
                    "pickup_location": "Airport"
                }
            ]
        }

    Result:

        New BookingCab row is created.

    ---------------------------------------------------------------------------
    Rule #4: Existing row missing from payload
    ---------------------------------------------------------------------------

    Existing DB:

        Traveller A
        Traveller B
        Traveller C

    Payload:

        {
            "travellers": [
                { "id": "TravellerA" },
                { "id": "TravellerC" }
            ]
        }

    Result:

        Traveller B association is deleted.

    ---------------------------------------------------------------------------
    Rule #5: Empty collection
    ---------------------------------------------------------------------------

    Request:

        {
            "travellers": []
        }

    Result:

        All BookingTraveller rows are removed.

    ===========================================================================
    IMPORTANT
    ===========================================================================

    BookingTravellerUpdate
    BookingCabUpdate
    BookingStayUpdate

    MUST contain:

        id: Optional[UUID] = None

    where the id refers to:

        BookingTraveller.id
        BookingCab.id
        BookingStay.id

    NOT:

        traveller_id
        cab_id
        stayunit_id

    ===========================================================================
    TRANSACTIONAL GUARANTEE
    ===========================================================================

    Entire update is executed in a single transaction.

    If any validation fails:

        - rollback everything
        - leave database unchanged
    """

    # -----------------------------------------------------------------------
    # Load booking
    # -----------------------------------------------------------------------
    booking = session.get(Booking, booking_id)

    if not booking:
        # don't reveal that the booking doesn't exist vs. not authorized
        raise HTTPException(
            status_code=403,
            detail="Not authorized to update this booking",
        )

    # -----------------------------------------------------------------------
    # Authorization
    #
    # Superuser:
    #   Can update any booking
    #
    # Staff:
    #   Can update only bookings owned by them
    # -----------------------------------------------------------------------
    if not current_user.is_superuser:

        staff_records = _get_staff_records(
            session,
            current_user.id,
        )

        if not staff_records:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to update booking",
            )

        staff_ids = {s.id for s in staff_records}

        if booking.travel_agency_staff_id not in staff_ids:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to update this booking",
            )

    # -----------------------------------------------------------------------
    # Convert incoming payload to dictionary
    # -----------------------------------------------------------------------
    update_data = booking_in.model_dump(exclude_unset=True)

    # -----------------------------------------------------------------------
    # Extract nested collections
    #
    # We handle these separately because they require synchronization logic.
    # -----------------------------------------------------------------------
    travellers_payload = update_data.pop("travellers", None)
    cabs_payload = update_data.pop("cabs", None)
    stays_payload = update_data.pop("stays", None)


    # -----------------------------------------------------------------------
    # Prevent ownership changes
    #
    # These fields are immutable once booking is created.
    # -----------------------------------------------------------------------
    for field in (
        "id",
        "travel_agency_id",
        "travel_agency_staff_id",
    ):
        update_data.pop(field, None)

    try:

        # ===================================================================
        # STEP 1
        # Update booking scalar fields
        # ===================================================================
        booking.sqlmodel_update(update_data)

        session.add(booking)

        # Flush so SQLAlchemy tracks updates immediately.
        session.flush()

        # ===================================================================
        # STEP 2
        # Synchronize Travellers
        # ===================================================================
        if travellers_payload is not None:

            # Existing BookingTraveller rows
            existing_rows = {
                str(row.id): row
                for row in booking.travellers
            }

            # Tracks rows present in payload
            seen_ids = set()

            for item in travellers_payload:

                row_id = item.get("id")

                # -----------------------------------------------------------
                # UPDATE EXISTING ROW
                # -----------------------------------------------------------
                if row_id:

                    row = existing_rows.get(str(row_id))

                    if not row:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Traveller relation {row_id} "
                                "does not belong to this booking"
                            ),
                        )
                    
                    # This will check if the traveller has a profile already, if and only if the traveller_id is provided. 
                    # Otherwise a new profile should be created
                    traveller_id = item.get("traveller_id")

                    if traveller_id:

                        traveller = session.get(
                            Profile,
                            traveller_id,
                        )

                        if not traveller:
                            raise HTTPException(
                                status_code=404,
                                detail=(
                                    f"Traveller profile "
                                    f"{traveller_id} not found"
                                ),
                            )

                        row.traveller_id = traveller_id

                    seen_ids.add(str(row.id))

                # -----------------------------------------------------------
                # CREATE NEW ROW
                # -----------------------------------------------------------
                else:

                    traveller_id = item.get("traveller_id")

                    if not traveller_id:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "traveller_id is required "
                                "for new traveller rows"
                            ),
                        )

                    traveller = session.get(
                        Profile,
                        traveller_id,
                    )

                    if not traveller:
                        raise HTTPException(
                            status_code=404,
                            detail=(
                                f"Traveller profile "
                                f"{traveller_id} not found"
                            ),
                        )

                    session.add(
                        BookingTraveller(
                            booking_id=booking.id,
                            traveller_id=traveller_id,
                        )
                    )

            # ---------------------------------------------------------------
            # DELETE REMOVED ROWS
            #
            # Any existing row not included in payload is removed.
            # ---------------------------------------------------------------
            for row_id, row in existing_rows.items():

                if row_id not in seen_ids:
                    session.delete(row)

        # ===================================================================
        # STEP 3
        # Synchronize Cabs
        # ===================================================================
        if cabs_payload is not None:

            existing_rows = {
                str(row.id): row
                for row in booking.cabs
            }

            seen_ids = set()

            for item in cabs_payload:

                row_id = item.get("id")

                # -----------------------------------------------------------
                # UPDATE EXISTING CAB
                # -----------------------------------------------------------
                if row_id:

                    row = existing_rows.get(str(row_id))

                    if not row:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Cab relation {row_id} "
                                "does not belong to this booking"
                            ),
                        )

                    # If cab changes, re-validate provider
                    if item.get("cab_id"):

                        cab = session.get(
                            Cab,
                            item["cab_id"],
                        )

                        if not cab:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Cab {item['cab_id']} not found",
                            )

                        row.cab_id = item["cab_id"]

                        provider_id = (
                            item.get("cab_provider_id")
                            or getattr(cab, "cab_provider_id", None)
                            or getattr(cab, "provider_id", None)
                        )

                        if not provider_id:
                            raise HTTPException(
                                status_code=400,
                                detail=(
                                    f"Cab provider id required "
                                    f"for cab {item['cab_id']}"
                                ),
                            )

                        row.cab_provider_id = provider_id

                    # Update mutable fields
                    for field in (
                        "pickup_time",
                        "pickup_location",
                        "drop_time",
                        "drop_location",
                        "driver_id",
                        "rate",
                        "status",
                    ):
                        if field in item:
                            setattr(row, field, item[field])

                    seen_ids.add(str(row.id))

                # -----------------------------------------------------------
                # CREATE NEW CAB
                # -----------------------------------------------------------
                else:

                    cab_id = item.get("cab_id")

                    if not cab_id:
                        raise HTTPException(
                            status_code=400,
                            detail="cab_id is required",
                        )

                    cab = session.get(Cab, cab_id)

                    if not cab:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Cab {cab_id} not found",
                        )

                    provider_id = (
                        item.get("cab_provider_id")
                        or getattr(cab, "cab_provider_id", None)
                        or getattr(cab, "provider_id", None)
                    )

                    if not provider_id:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Cab provider id required "
                                f"for cab {cab_id}"
                            ),
                        )

                    session.add(
                        BookingCab(
                            booking_id=booking.id,
                            cab_id=cab_id,
                            cab_provider_id=provider_id,
                            pickup_time=item.get("pickup_time"),
                            pickup_location=item.get("pickup_location"),
                            drop_time=item.get("drop_time"),
                            drop_location=item.get("drop_location"),
                            driver_id=item.get("driver_id"),
                            rate=item.get("rate"),
                            status=item.get("status"),
                        )
                    )

            # Delete removed rows
            for row_id, row in existing_rows.items():

                if row_id not in seen_ids:
                    session.delete(row)

        # ===================================================================
        # STEP 4
        # Synchronize Stays
        # ===================================================================
        if stays_payload is not None:

            existing_rows = {
                str(row.id): row
                for row in booking.stays
            }

            seen_ids = set()

            for item in stays_payload:

                row_id = item.get("id")

                # -----------------------------------------------------------
                # UPDATE EXISTING STAY
                # -----------------------------------------------------------
                if row_id:

                    row = existing_rows.get(str(row_id))

                    if not row:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Stay relation {row_id} "
                                "does not belong to this booking"
                            ),
                        )

                    for field in (
                        "stayunit_id",
                        "stay_provider_id",
                        "check_in",
                        "check_out",
                        "room_type",
                        "rate",
                        "status",
                    ):
                        if field in item:
                            setattr(row, field, item[field])

                    seen_ids.add(str(row.id))

                # -----------------------------------------------------------
                # CREATE NEW STAY
                # -----------------------------------------------------------
                else:

                    session.add(
                        BookingStay(
                            booking_id=booking.id,
                            stayunit_id=item.get("stayunit_id"),
                            stay_provider_id=item.get("stay_provider_id"),
                            check_in=item.get("check_in"),
                            check_out=item.get("check_out"),
                            room_type=item.get("room_type"),
                            rate=item.get("rate"),
                            status=item.get("status"),
                        )
                    )

            # Delete removed rows
            for row_id, row in existing_rows.items():

                if row_id not in seen_ids:
                    session.delete(row)

        # ===================================================================
        # STEP 5
        # Commit transaction
        # ===================================================================
        session.commit()

    except HTTPException:
        session.rollback()
        raise

    except Exception:
        session.rollback()
        raise

    # -----------------------------------------------------------------------
    # Reload booking with all nested relationships
    # -----------------------------------------------------------------------
    stmt = (
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.travellers)
            .selectinload(BookingTraveller.traveller),

            selectinload(Booking.cabs)
            .selectinload(BookingCab.cab),

            selectinload(Booking.cabs)
            .selectinload(BookingCab.driver)
            .selectinload(Driver.profile),

            selectinload(Booking.stays)
            .selectinload(BookingStay.stayunit),
        )
    )

    return session.exec(stmt).first()

__all__ = ["router"]
