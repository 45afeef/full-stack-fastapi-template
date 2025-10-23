from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel


class CabCreate(SQLModel):
    vehicle_type: str
    vehicle_number: str


class CabPublic(SQLModel):
    id: UUID
    provider_id: UUID
    vehicle_type: str
    vehicle_number: str


class DriverCreate(SQLModel):
    user_id: UUID


class DriverPublic(SQLModel):
    user_id: UUID
    provider_id: UUID
    id: Optional[UUID]


__all__ = ["CabCreate", "CabPublic", "DriverCreate", "DriverPublic"]
