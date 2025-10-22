from typing import Optional, List
from uuid import UUID
from sqlmodel import SQLModel

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


__all__ = [
    "StayUnitCreate",
    "StayUnitPublic",
    "UnitFilterParams",
    "UnitsList",
]
