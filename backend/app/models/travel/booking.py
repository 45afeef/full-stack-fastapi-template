from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlmodel import Column, DateTime, func

from .enums import BookingStatus, RoomType


class Booking(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    traveler_id: UUID = Field(foreign_key="profile.id")
    travel_agency_id: Optional[UUID] = Field(default=None, foreign_key="travelagency.id")
    travel_agency_staff_id: Optional[UUID] = Field(default=None, foreign_key="travelagencystaff.id")
    enquiry_id: Optional[UUID] = Field(default=None, foreign_key="enquirydetails.id")
    booking_date: Optional[datetime] = Field(default=None)
    status: Optional[BookingStatus] = Field(default=None)
    total_amount: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class BookingTraveller(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    booking_id: UUID = Field(foreign_key="booking.id")
    traveller_id: UUID = Field(foreign_key="profile.id")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

class BookingCab(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    cab_id: UUID = Field(foreign_key="cab.id")
    booking_id: UUID = Field(foreign_key="booking.id")
    cab_provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")
    pickup_time: Optional[datetime] = Field(default=None)
    pickup_location: Optional[str] = Field(default=None)
    drop_time: Optional[datetime] = Field(default=None)
    drop_location: Optional[str] = Field(default=None)
    driver_id: Optional[UUID] = Field(default=None, foreign_key="driver.user_id")
    rate: Optional[int] = Field(default=None)
    status: Optional[BookingStatus] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

class BookingStay(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    stayunit_id: UUID = Field(foreign_key="stayunit.id")
    booking_id: UUID = Field(foreign_key="booking.id")
    stay_provider_id: UUID = Field(foreign_key="stayserviceprovider.provider_id")
    check_in: Optional[datetime] = Field(default=None)
    check_out: Optional[datetime] = Field(default=None)
    room_type: Optional[RoomType] = Field(default=None)
    rate: Optional[int] = Field(default=None)
    status: Optional[BookingStatus] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


__all__ = [
    "Booking",
    "BookingTraveller",
    "BookingCab",
    "BookingStay",
]
