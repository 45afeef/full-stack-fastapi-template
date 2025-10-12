from typing import TYPE_CHECKING, Optional
import uuid
from datetime import date

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


class ProfileCreate(ProfileBase):
    user_id: uuid.UUID = Field(foreign_key="user.id")


class ProfileUpdate(ProfileBase):
    pass


class Profile(ProfileBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE")
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)

    user: Optional["User"] = Relationship(back_populates="profile", sa_relationship_kwargs={"uselist": False})


class ProfilePublic(ProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID


class ProfilesPublic(SQLModel):
    data: list[ProfilePublic]
    count: int


__all__ = ["Profile", "ProfileCreate", "ProfileUpdate", "ProfilePublic", "ProfilesPublic"]
