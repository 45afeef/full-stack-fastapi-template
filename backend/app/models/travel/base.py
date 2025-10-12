from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import Column, DateTime, func
from sqlmodel import SQLModel, Field


class TimestampMixin(SQLModel):
    """Mixin to add created_at and updated_at timestamps backed by SQL columns.

    These use server defaults so the database will populate/refresh the values
    automatically (using NOW()) on insert and update.
    """

    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


__all__ = ["TimestampMixin"]
