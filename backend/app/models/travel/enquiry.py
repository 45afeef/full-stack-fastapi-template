from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlmodel import Column, DateTime, func


class EnquiryDetails(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)    

    adult_men_count: Optional[int] = Field(default=None)
    adult_women_count: Optional[int] = Field(default=None)
    adult_no_binary_count: Optional[int] = Field(default=None)
    kids_below_12_boy_count: Optional[int] = Field(default=None)
    kids_below_12_girl_count: Optional[int] = Field(default=None)

    check_in: Optional[datetime] = Field(default=None)
    check_out: Optional[datetime] = Field(default=None)

    pickup_location: Optional[str] = Field(default=None)
    drop_location: Optional[str] = Field(default=None)

    handled_by: Optional[UUID] = Field(default=None, foreign_key="travelagencystaff.id")
    enquired_by: Optional[UUID] = Field(default=None, foreign_key="profile.id")

    created_at: Optional[datetime] = Field(default=None,sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None,sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


__all__ = ["EnquiryDetails"]
