from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field


class Location(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    latitude: float = Field(nullable=False)
    longitude: float = Field(nullable=False)


__all__ = ["Location"]
