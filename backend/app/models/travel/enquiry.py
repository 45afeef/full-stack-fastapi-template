from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field


class EnquiryDetails(SQLModel, table=True):
    id: UUID = Field(default=None, primary_key=True)
    adult_men_count: Optional[int] = Field(default=None)
    adult_women_count: Optional[int] = Field(default=None)
    adult_no_binary_count: Optional[int] = Field(default=None)
    kids_below_12_boy_count: Optional[int] = Field(default=None)
    kids_below_12_girl_count: Optional[int] = Field(default=None)
    check_in: Optional[datetime] = Field(default=None)
    check_out: Optional[datetime] = Field(default=None)
    pickup_location: Optional[str] = Field(default=None)
    drop_location: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    handled_by: Optional[UUID] = Field(default=None)
    enquired_by: Optional[UUID] = Field(default=None, foreign_key="userprofile.id")


__all__ = ["EnquiryDetails"]
