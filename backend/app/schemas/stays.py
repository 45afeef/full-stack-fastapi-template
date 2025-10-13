from typing import Optional, List
from uuid import UUID
from sqlmodel import SQLModel
from datetime import datetime


class ProviderCreate(SQLModel):
    provider_type: str
    provider_name: str
    location_id: Optional[UUID] = None
    owner_id: UUID
    created_by: UUID


class ProviderPublic(SQLModel):
    id: UUID
    provider_type: str
    provider_name: str
    location_id: Optional[UUID] = None


class StayUnitCreate(SQLModel):
    name: str
    description: Optional[str] = None
    room_rate: Optional[int] = None
    per_head_rate: Optional[int] = None
    max_occupancy: Optional[int] = None


class StayUnitPublic(SQLModel):
    id: UUID
    name: str
    description: Optional[str] = None
    room_rate: Optional[int] = None
    per_head_rate: Optional[int] = None
    max_occupancy: Optional[int] = None
    provider_id: UUID


class AgencyCreate(SQLModel):
    agency_name: str
    contact_email: Optional[str] = None
    location_id: Optional[UUID] = None
    created_by: UUID


class AgencyStaffCreate(SQLModel):
    user_id: UUID
    role: Optional[str] = None


class UnitFilterParams(SQLModel):
    provider_id: Optional[UUID] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    amenity: Optional[str] = None
    limit: int = 100
    offset: int = 0


class UnitsList(SQLModel):
    data: List[StayUnitPublic]
    count: int


__all__ = [
    "ProviderCreate",
    "ProviderPublic",
    "StayUnitCreate",
    "StayUnitPublic",
    "AgencyCreate",
    "AgencyStaffCreate",
    "UnitFilterParams",
    "UnitsList",
]
