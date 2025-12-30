from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel import Column, DateTime, func
from .enums import VehicleType


class Cab(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")
    vehicle_type: VehicleType = Field(nullable=False)
    vehicle_number: str = Field(unique=True, nullable=False)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    minimum_rate: int = Field(nullable=False)
    km_for_minimum_rate: int = Field(nullable=False)
    per_km_rate: int = Field(nullable=False)
    capacity: int = Field(nullable=False)
    name: str = Field(nullable=False)
    company_model: str = Field(nullable=False)
    color: str = Field(nullable=False)



class Driver(SQLModel, table=True): 
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(primary_key=True, foreign_key="user.id")
    profile_id: UUID = Field(foreign_key="profile.id")
    provider_id: UUID = Field(foreign_key="cabserviceprovider.provider_id")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )
    

__all__ = ["Cab", "Driver"]
