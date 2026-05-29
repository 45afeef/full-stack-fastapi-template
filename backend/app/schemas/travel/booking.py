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


# Response schemas with nested data

class ProfileRead(SQLModel):
    """Profile data for travellers"""
    id: UUID
    user_id: Optional[UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def full_name(self) -> str:
        """Return full name of traveller"""
        first = self.first_name or ""
        last = self.last_name or ""
        return f"{first} {last}".strip() or "Unknown"


class BookingTravellerRead(SQLModel):
    """BookingTraveller with traveller profile data"""
    id: UUID
    booking_id: UUID
    traveller_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    traveller: Optional[ProfileRead] = None
    
    @property
    def traveller_name(self) -> str:
        """Return traveller name if available"""
        if self.traveller:
            return self.traveller.full_name
        return "Unknown"
    
    @property
    def traveller_phone(self) -> Optional[str]:
        """Return traveller phone if available"""
        return self.traveller.phone if self.traveller else None


class ServiceProviderRead(SQLModel):
    """Service provider data"""
    id: UUID
    provider_name: str
    provider_type: Optional[str] = None
    location_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DriverRead(SQLModel):
    """Driver data with profile information"""
    id: UUID
    profile_id: Optional[UUID] = None
    provider_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    profile: Optional[ProfileRead] = None
    
    @property
    def driver_name(self) -> str:
        """Return driver name if available"""
        if self.profile:
            return self.profile.full_name
        return "Unknown"
    
    @property
    def driver_phone(self) -> Optional[str]:
        """Return driver phone if available"""
        return self.profile.phone if self.profile else None


class CabRead(SQLModel):
    """Cab data with all relevant details"""
    id: UUID
    provider_id: Optional[UUID] = None
    name: str
    vehicle_number: str
    vehicle_type: Optional[str] = None
    company_model: Optional[str] = None
    color: Optional[str] = None
    capacity: Optional[int] = None
    minimum_rate: Optional[int] = None
    per_km_rate: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BookingCabRead(SQLModel):
    """BookingCab with cab, driver, and provider details"""
    id: UUID
    booking_id: UUID
    cab_id: UUID
    cab_provider_id: UUID
    pickup_time: Optional[datetime] = None
    pickup_location: Optional[str] = None
    drop_time: Optional[datetime] = None
    drop_location: Optional[str] = None
    driver_id: Optional[UUID] = None
    rate: Optional[int] = None
    status: Optional[BookingStatus] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Nested data
    cab: Optional[CabRead] = None
    driver: Optional[DriverRead] = None
    
    # Human-friendly properties
    @property
    def cab_name(self) -> str:
        """Return cab name"""
        if self.cab:
            return self.cab.name
        return "Unknown"
    
    @property
    def cab_vehicle_number(self) -> str:
        """Return vehicle number"""
        if self.cab:
            return self.cab.vehicle_number
        return "Unknown"
    
    @property
    def cab_capacity(self) -> Optional[int]:
        """Return cab capacity"""
        return self.cab.capacity if self.cab else None
    
    @property
    def driver_name(self) -> str:
        """Return driver name"""
        if self.driver:
            return self.driver.driver_name
        return "Not Assigned"
    
    @property
    def driver_phone(self) -> Optional[str]:
        """Return driver phone"""
        return self.driver.driver_phone if self.driver else None


class StayUnitRead(SQLModel):
    """StayUnit data with all relevant details"""
    id: UUID
    name: str
    description: Optional[str] = None
    provider_id: Optional[UUID] = None
    room_rate: Optional[int] = None
    room_rate_occupancy: Optional[int] = None
    per_head_rate: Optional[int] = None
    max_occupancy: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BookingStayRead(SQLModel):
    """BookingStay with stay unit and provider details"""
    id: UUID
    booking_id: UUID
    stayunit_id: Optional[UUID] = None
    stay_provider_id: UUID
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    room_type: Optional[str] = None
    rate: Optional[int] = None
    status: Optional[BookingStatus] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Nested data
    stayunit: Optional[StayUnitRead] = None
    
    # Human-friendly properties
    @property
    def stay_name(self) -> str:
        """Return stay unit name"""
        if self.stayunit:
            return self.stayunit.name
        return "Unknown"
    
    @property
    def stay_description(self) -> Optional[str]:
        """Return stay description"""
        return self.stayunit.description if self.stayunit else None
    
    @property
    def max_occupancy(self) -> Optional[int]:
        """Return max occupancy"""
        return self.stayunit.max_occupancy if self.stayunit else None
    
    @property
    def stay_room_rate(self) -> Optional[int]:
        """Return room rate"""
        return self.stayunit.room_rate if self.stayunit else None


class BookingRead(SQLModel):
    """Complete booking with all nested data and human-friendly information"""
    id: UUID
    travel_agency_id: Optional[UUID] = None
    travel_agency_staff_id: Optional[UUID] = None
    enquiry_id: Optional[UUID] = None
    booking_date: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    total_amount: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    travellers: list[BookingTravellerRead] = []
    cabs: list[BookingCabRead] = []
    stays: list[BookingStayRead] = []
    
    # Human-friendly summary properties
    @property
    def traveller_names(self) -> list[str]:
        """Return list of traveller names"""
        return [t.traveller_name for t in self.travellers]
    
    @property
    def traveller_count(self) -> int:
        """Return count of travellers"""
        return len(self.travellers)
    
    @property
    def cab_count(self) -> int:
        """Return count of cabs"""
        return len(self.cabs)
    
    @property
    def stay_count(self) -> int:
        """Return count of stays"""
        return len(self.stays)


__all__ = [
    "BookingCreate",
    "BookingUpdate",
    "BookingRead",
    "BookingTravellerCreate",
    "BookingTravellerRead",
    "BookingCabCreate",
    "BookingCabRead",
    "BookingStayCreate",
    "BookingStayRead",
    "ProfileRead",
    "DriverRead",
    "CabRead",
    "StayUnitRead",
]
