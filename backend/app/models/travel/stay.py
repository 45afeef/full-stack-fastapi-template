from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field
from .enums import AmenityScope


class StayUnit(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    provider_id: UUID = Field(foreign_key="stayserviceprovider.provider_id")
    room_rate: Optional[int] = Field(default=None)
    per_head_rate: Optional[int] = Field(default=None)
    max_occupancy: Optional[int] = Field(default=None)


class StayAmenity(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    stay_service_provider_id: UUID = Field(foreign_key="stayserviceprovider.provider_id")
    stay_unit_id: UUID = Field(foreign_key="stayunit.id")
    amenity_scope: AmenityScope = Field(nullable=False)
    amenity: str = Field(nullable=False)


__all__ = ["StayUnit", "StayAmenity"]
