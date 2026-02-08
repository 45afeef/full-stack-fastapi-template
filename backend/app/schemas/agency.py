from typing import Optional, List
from uuid import UUID

from pydantic import EmailStr
from sqlmodel import SQLModel
from datetime import datetime
from app.models.travel.enums import StaffRole


class AgencyCreate(SQLModel):
    agency_name: str
    contact_email: Optional[EmailStr]
    location_id: Optional[UUID] = None

class AgencyPublic(SQLModel):
    id: UUID
    agency_name: str
    contact_email: Optional[str] = None
    location_id: Optional[UUID] = None

class AgencyDetail(AgencyPublic):
    created_by: UUID
    created_at: Optional[datetime] = None

class AgencyUpdate(SQLModel):
    agency_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    location_id: Optional[UUID] = None

class AgencyStaffCreate(SQLModel):
    user_id: UUID
    role: Optional[StaffRole] = None

class AgencyStaffPublic(SQLModel):
    id: UUID
    user_id: UUID
    travel_agency_id: UUID
    role: Optional[StaffRole] = None

class AgencyStaffUpdate(SQLModel):
    role: Optional[StaffRole] = None


__all__ = [
    "AgencyCreate",
    "AgencyStaffCreate",
]
