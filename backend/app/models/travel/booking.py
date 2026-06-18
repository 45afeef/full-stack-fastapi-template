from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel import Column, DateTime, func

from .enums import BookingStatus, RoomType

if TYPE_CHECKING:
    from app.models.travel.providers import TravelAgency, TravelAgencyStaff
    from app.models.travel.enquiry import EnquiryDetails
    from app.models.user.profile import Profile
    from app.models.travel.cab import Cab, Driver
    from app.models.travel.stay import StayUnit
    from app.models.travel.providers import CabServiceProvider, StayServiceProvider


class Booking(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    travel_agency_id: Optional[UUID] = Field(default=None, foreign_key="travelagency.id")
    travel_agency_staff_id: Optional[UUID] = Field(default=None, foreign_key="travelagencystaff.id")
    enquiry_id: Optional[UUID] = Field(default=None, foreign_key="enquirydetails.id")
    booking_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
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
    
    # Relationships
    travellers: list["BookingTraveller"] = Relationship(back_populates="booking", cascade_delete=True)
    cabs: list["BookingCab"] = Relationship(back_populates="booking", cascade_delete=True)
    stays: list["BookingStay"] = Relationship(back_populates="booking", cascade_delete=True)


class BookingTraveller(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
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
    
    # Relationships
    booking: "Booking" = Relationship(back_populates="travellers")
    traveller: "Profile" = Relationship()

class BookingCab(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cab_id: UUID = Field(foreign_key="cab.id")
    booking_id: UUID = Field(foreign_key="booking.id")
    cab_provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")
    pickup_time: Optional[datetime] = Field(default=None)
    pickup_location: Optional[str] = Field(default=None)
    drop_time: Optional[datetime] = Field(default=None)
    drop_location: Optional[str] = Field(default=None)
    driver_id: Optional[UUID] = Field(default=None, foreign_key="driver.id")
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
    
    # Relationships
    booking: "Booking" = Relationship(back_populates="cabs")
    cab: "Cab" = Relationship()
    driver: Optional["Driver"] = Relationship()
    cab_provider: Optional["CabServiceProvider"] = Relationship()

class BookingStay(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    stayunit_id: UUID = Field(default=None,foreign_key="stayunit.id")
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
    
    # Relationships
    booking: "Booking" = Relationship(back_populates="stays")
    stayunit: Optional["StayUnit"] = Relationship()
    stay_provider: Optional["StayServiceProvider"] = Relationship()


__all__ = [
    "Booking",
    "BookingTraveller",
    "BookingCab",
    "BookingStay",
]
