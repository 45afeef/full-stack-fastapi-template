from typing import Literal, Optional, Union
from uuid import UUID
from sqlmodel import SQLModel

from app.models.travel.enums import ServiceProviderType


# --------- Base Provider Create Models ---------
class BaseProviderCreate(SQLModel):
    provider_name: str
    latitude: float  # Mandatory
    longitude: float  # Mandatory
    owner_id: UUID
    created_by: UUID


class CabProviderCreate(BaseProviderCreate):
    provider_type: Literal["CAB"]


class StayProviderCreate(BaseProviderCreate):
    provider_type: Literal["STAY"]
    property_type: Optional[str] = None
    room_count: Optional[int] = None
    optimal_occupancy: Optional[int] = None
    max_occupancy: Optional[int] = None


ProviderCreate = Union[CabProviderCreate, StayProviderCreate]


# --------- Public (Response) Models ---------
class BaseProviderPublic(SQLModel):
    id: UUID
    provider_name: str
    provider_type: ServiceProviderType
    location_id: Optional[UUID] = None


class CabProviderPublic(BaseProviderPublic):
    provider_type: Literal["CAB"]


class StayProviderPublic(BaseProviderPublic):
    provider_type: Literal["STAY"]
    property_type: Optional[str] = None
    room_count: Optional[int] = None
    optimal_occupancy: Optional[int] = None
    max_occupancy: Optional[int] = None


ProviderPublic = Union[CabProviderPublic, StayProviderPublic]


class PublicStayProviderList(SQLModel):
    data: list[StayProviderPublic]
    count: int
    


__all__ = [
    "ProviderCreate",
    "ProviderPublic",
    "PublicStayProviderList",
]
