from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field


class TimestampMixin(SQLModel):
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


__all__ = ["TimestampMixin"]
