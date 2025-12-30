from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from .enums import AmenityScope
from sqlmodel import Column, DateTime, func

class StayUnit(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    provider_id: UUID = Field(foreign_key="stayserviceprovider.provider_id")
    room_rate: Optional[int] = Field(default=None)
    room_rate_occupancy: Optional[int] = Field(default=None)
    per_head_rate: Optional[int] = Field(default=None)
    max_occupancy: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class StayAmenity(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    stay_service_provider_id: UUID = Field(foreign_key="stayserviceprovider.provider_id")
    stay_unit_id: UUID = Field(foreign_key="stayunit.id")
    amenity_scope: AmenityScope = Field(nullable=False)
    amenity: str = Field(nullable=False)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


__all__ = ["StayUnit", "StayAmenity"]
