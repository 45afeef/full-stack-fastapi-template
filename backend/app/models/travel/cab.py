from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from .enums import VehicleType


class Cab(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")
    vehicle_type: VehicleType = Field(nullable=False)
    vehicle_number: str = Field(unique=True, nullable=False)


class Driver(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(primary_key=True, foreign_key="user.id")
    profile_id: UUID = Field(foreign_key="profile.id")
    provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")


__all__ = ["Cab", "Driver"]
