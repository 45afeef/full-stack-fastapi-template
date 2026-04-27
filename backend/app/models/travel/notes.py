from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlmodel import Column, DateTime, func

class Note(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    created_by: UUID = Field(foreign_key="user.id")
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


class PhoneNote(SQLModel, table=True):
    phone_id: UUID = Field(foreign_key="phonenumber.id", primary_key=True)
    note_id: UUID = Field(foreign_key="note.id", primary_key=True)


class ProfileNote(SQLModel, table=True):
    profile_id: UUID = Field(foreign_key="profile.id", primary_key=True)
    note_id: UUID = Field(foreign_key="note.id", primary_key=True)


class BookingNote(SQLModel, table=True):
    booking_id: UUID = Field(foreign_key="booking.id", primary_key=True)
    note_id: UUID = Field(foreign_key="note.id", primary_key=True)


__all__ = ["Note", "PhoneNote", "ProfileNote", "BookingNote"]
