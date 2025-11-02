from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.travel.enums import BookingStatus
from sqlmodel import SQLModel


class BookingTravellerCreate(SQLModel):
    traveller_id: UUID


class BookingCabCreate(SQLModel):
    cab_id: UUID
    cab_provider_id: Optional[UUID] = None
    pickup_time: Optional[datetime] = None
    pickup_location: Optional[str] = None
    drop_time: Optional[datetime] = None
    drop_location: Optional[str] = None
    driver_id: Optional[UUID] = None
    rate: Optional[int] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None


class BookingStayCreate(SQLModel):
    stayunit_id: UUID
    stay_provider_id: Optional[UUID] = None
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    room_type: Optional[str] = None
    rate: Optional[int] = None
    status: Optional[BookingStatus] = None


class BookingCreate(SQLModel):
    traveler_id: UUID
    booking_date: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    total_amount: Optional[int] = None
    travel_agency_id: Optional[UUID] = None
    # nested sub-resources
    travellers: Optional[list[BookingTravellerCreate]] = None
    cabs: Optional[list[BookingCabCreate]] = None
    stays: Optional[list[BookingStayCreate]] = None


class BookingUpdate(SQLModel):
    booking_date: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    total_amount: Optional[int] = None


__all__ = [
    "BookingCreate",
    "BookingUpdate",
    "BookingTravellerCreate",
    "BookingCabCreate",
    "BookingStayCreate",
]
