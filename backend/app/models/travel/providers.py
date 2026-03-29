from datetime import datetime
from  typing import TYPE_CHECKING

from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlmodel import Column, DateTime, func

from .enums import ServiceProviderType, StaffRole


class ServiceProvider(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_type: ServiceProviderType = Field(nullable=False)
    provider_name: str = Field(nullable=False)
    location_id: Optional[UUID] = Field(default=None, foreign_key="location.id")
    owner_id: UUID = Field(foreign_key="user.id")
    created_by: UUID = Field(foreign_key="user.id")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    cab_provider: Optional["CabServiceProvider"] = Relationship(back_populates="provider")
    stay_provider: Optional["StayServiceProvider"] = Relationship(back_populates="provider")

class CabServiceProvider(SQLModel, table=True):
    provider_id: UUID = Field(primary_key=True, foreign_key="serviceprovider.id")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    provider: "ServiceProvider" = Relationship(back_populates="cab_provider")


class StayServiceProvider(SQLModel, table=True):
    provider_id: UUID = Field(primary_key=True, foreign_key="serviceprovider.id")
    property_type: Optional[str] = Field(default=None)
    room_count: Optional[int] = Field(default=None)
    optimal_occupancy: Optional[int] = Field(default=None)
    max_occupancy: Optional[int] = Field(default=None)

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    provider: "ServiceProvider" = Relationship(back_populates="stay_provider")

class TravelAgency(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agency_name: str = Field(nullable=False)
    contact_email: Optional[str] = Field(nullable=False)
    location_id: Optional[UUID] = Field(default=None, foreign_key="location.id")
    created_by: UUID = Field(foreign_key="user.id")

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class TravelAgencyStaff(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    travel_agency_id: UUID = Field(foreign_key="travelagency.id")
    role: Optional[StaffRole] = Field(default=None)
    joined_at: Optional[str] = Field(default=None)
    resigned_at: Optional[str] = Field(default=None)
    resigning_reason: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


__all__ = [
    "ServiceProvider",
    "CabServiceProvider",
    "StayServiceProvider",
    "TravelAgency",
    "TravelAgencyStaff",
]
