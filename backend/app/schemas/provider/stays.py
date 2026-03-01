from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel

from app.models.travel.enums import AmenityScope

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


class StayUnitWithDistance(StayUnitPublic):
    # distance in kilometers from query point; optional so old clients keep working
    distance_km: float | None = None


class UnitsListWithDistance(SQLModel):
    data: List[StayUnitWithDistance]
    count: int


# ------------- amenity schemas ----------------

class StayAmenityCreate(SQLModel):
    amenity_scope: AmenityScope
    amenity: str


class StayAmenityPublic(StayAmenityCreate):
    id: UUID
    stay_unit_id: UUID
    stay_service_provider_id: UUID


class StayAmenitiesList(SQLModel):
    data: List[StayAmenityPublic]
    count: int


__all__ = [
    "StayUnitCreate",
    "StayUnitPublic",
    "UnitFilterParams",
    "UnitsList",
    "StayAmenityCreate",
    "StayAmenityPublic",
    "StayAmenitiesList",
]