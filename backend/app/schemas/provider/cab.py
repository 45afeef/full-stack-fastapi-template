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
    user_id: UUID = None
    profile_id: UUID


class DriverPublic(SQLModel):
    user_id: UUID
    provider_id: UUID
    id: Optional[UUID]


__all__ = ["CabCreate", "CabPublic", "DriverCreate", "DriverPublic"]


class CabsList(SQLModel):
    data: list[CabPublic]
    count: int


class DriversList(SQLModel):
    data: list[DriverPublic]
    count: int


__all__ += ["CabsList", "DriversList"]
