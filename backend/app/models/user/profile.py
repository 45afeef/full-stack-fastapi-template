from typing import TYPE_CHECKING, Optional
import uuid
from datetime import date, datetime
from sqlmodel import Column, DateTime, func

from pydantic import EmailStr

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class ProfileBase(SQLModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    middle_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[date] = Field(default=None)
    profile_picture: Optional[str] = Field(default=None, max_length=255)
    bio: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    zip_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)
    primary_phone_number: Optional[str] = Field(unique=True, index=True, max_length=20)
    secondary_phone_number: Optional[str] = Field(default=None, unique=True, index=True, max_length=20)
    primary_email: Optional[EmailStr] = Field(default=None, unique=True, index=True, max_length=100)
    secondary_email: Optional[EmailStr] = Field(default=None, unique=True, index=True, max_length=100)
    created_by_user_id: Optional[uuid.UUID] = Field(default=None)


class ProfileCreate(ProfileBase):
    user_id: uuid.UUID = Field(foreign_key="user.id")


class ProfileUpdate(ProfileBase):
    pass


class Profile(ProfileBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE")    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )


    user: Optional["User"] = Relationship(back_populates="profile", sa_relationship_kwargs={"uselist": False})


class ProfilePublic(ProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID


class ProfilesPublic(SQLModel):
    data: list[ProfilePublic]
    count: int


__all__ = ["Profile", "ProfileCreate", "ProfileUpdate", "ProfilePublic", "ProfilesPublic"]
