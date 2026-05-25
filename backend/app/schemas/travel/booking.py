from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.travel.enums import BookingStatus
from sqlmodel import SQLModel
from pydantic import model_validator


class BookingTravellerCreate(SQLModel):
    traveller_id: Optional[UUID] = None
    traveller_name: Optional[str] = None
    traveller_phone: Optional[str] = None

    @model_validator(mode="after")
    def validate_traveller_input(self):
        has_id = self.traveller_id is not None

        has_new_traveller_data = (
            self.traveller_name is not None and
            self.traveller_phone is not None
        )

        if not has_id and not has_new_traveller_data:
            raise ValueError(
                "Provide either traveller_id OR both traveller_name and traveller_phone"
            )

        if has_id and has_new_traveller_data:
            raise ValueError(
                "Provide either traveller_id OR traveller_name/traveller_phone, not both"
            )

        return self


class BookingCabCreate(SQLModel):
    cab_id: Optional[UUID] = None
    cab_provider_id: Optional[UUID] = None
    pickup_time: Optional[datetime] = None
    pickup_location: Optional[str] = None
    drop_time: Optional[datetime] = None
    drop_location: Optional[str] = None
    driver_id: Optional[UUID] = None
    rate: Optional[int] = None # This is the cost to the agency, not the amount charged to the customer
    status: Optional[BookingStatus] = None


class BookingStayCreate(SQLModel):
    stayunit_id: Optional[UUID] = None
    stay_provider_id: Optional[UUID] = None
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    room_type: Optional[str] = None
    rate: Optional[int] = None # This is the cost to the agency, not the amount charged to the customer
    status: Optional[BookingStatus] = None


class BookingCreate(SQLModel):
    booking_date: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    total_amount: Optional[int] = None # This is charged to the customer, (not the agency cost)
    travel_agency_id: Optional[UUID] = None
    # nested sub-resources
    travellers: Optional[list[BookingTravellerCreate]] = None
    cabs: Optional[list[BookingCabCreate]] = None
    stays: Optional[list[BookingStayCreate]] = None


class BookingUpdate(BookingCabCreate):
    pass


__all__ = [
    "BookingCreate",
    "BookingUpdate",
    "BookingTravellerCreate",
    "BookingCabCreate",
    "BookingStayCreate",
]
