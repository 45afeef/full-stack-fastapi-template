from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field


class Note(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    title: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    created_by: UUID = Field(foreign_key="user.id")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


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
