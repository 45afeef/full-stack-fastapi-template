from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel

class ProviderCreate(SQLModel):
    provider_type: str
    provider_name: str
    location_id: Optional[UUID] = None
    owner_id: UUID
    created_by: UUID

class ProviderPublic(SQLModel):
    id: UUID
    provider_type: str
    provider_name: str
    location_id: Optional[UUID] = None

__all__ = [
    "ProviderCreate",
    "ProviderPublic",
]
