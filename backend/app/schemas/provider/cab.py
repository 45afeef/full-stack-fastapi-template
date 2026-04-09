from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel


class CabCreate(SQLModel):
    vehicle_type: str
    vehicle_number: str
    minimum_rate: float
    km_for_minimum_rate: float
    per_km_rate: float
    capacity: int
    name: str
    company_model: str
    color: str


class CabPublic(SQLModel):
    id: UUID
    provider_id: UUID
    vehicle_type: str
    vehicle_number: str
    minimum_rate: float
    km_for_minimum_rate: float
    per_km_rate: float
    capacity: int
    name: str
    company_model: str
    color: str


class DriverCreate(SQLModel):
    user_id: Optional[UUID] = None
    profile_id: UUID


class DriverPublic(SQLModel):
    # user_id is optional because drivers may be created without an associated
    # user account. response validation was previously failing when user_id was
    # None.
    user_id: Optional[UUID] = None
    provider_id: UUID
    profile_id: UUID
    id: Optional[UUID] = None

    # driver contact/profile details included in query responses so clients
    # can avoid extra nested calls for profile/user lookups.
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    primary_phone_number: Optional[str] = None
    secondary_phone_number: Optional[str] = None
    primary_email: Optional[str] = None
    secondary_email: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = ["CabCreate", "CabPublic", "DriverCreate", "DriverPublic"]


class CabsList(SQLModel):
    data: list[CabPublic]
    count: int


class DriversList(SQLModel):
    data: list[DriverPublic]
    count: int


__all__ += ["CabsList", "DriversList"]
