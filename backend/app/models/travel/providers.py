from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Relationship
from app.models.user.user import User
from .enums import ServiceProviderType


class ServiceProvider(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    provider_type: ServiceProviderType = Field(nullable=False)
    provider_name: str = Field(nullable=False)
    location_id: Optional[UUID] = Field(default=None, foreign_key="location.id")
    owner_id: UUID = Field(foreign_key="user.id")
    created_by: UUID = Field(foreign_key="user.id")
    created_at: Optional[str] = Field(default=None)


class CabServiceProvider(SQLModel, table=True):
    provider_id: UUID = Field(primary_key=True, foreign_key="serviceprovider.id")
    updated_at: Optional[str] = Field(default=None)


class StayServiceProvider(SQLModel, table=True):
    provider_id: UUID = Field(primary_key=True, foreign_key="serviceprovider.id")
    property_type: Optional[str] = Field(default=None)
    room_count: Optional[int] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)


class TravelAgency(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    agency_name: str = Field(nullable=False)
    contact_email: Optional[str] = Field(default=None)
    location_id: Optional[UUID] = Field(default=None, foreign_key="location.id")
    created_by: UUID = Field(foreign_key="user.id")
    created_at: Optional[str] = Field(default=None)


class TravelAgencyStaff(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    travel_agency_id: UUID = Field(foreign_key="travelagency.id")
    role: Optional[str] = Field(default=None)
    joined_at: Optional[str] = Field(default=None)
    resigned_at: Optional[str] = Field(default=None)
    resigning_reason: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)


__all__ = [
    "ServiceProvider",
    "CabServiceProvider",
    "StayServiceProvider",
    "TravelAgency",
    "TravelAgencyStaff",
]
