from typing import TYPE_CHECKING, Optional
import uuid

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


class UserProfileBase(SQLModel):
    """Shared properties for user profile used in API schemas."""

    profile_picture: Optional[str] = Field(default=None, max_length=255)
    bio: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    zip_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)


class UserProfileCreate(UserProfileBase):
    user_id: uuid.UUID = Field(foreign_key="user.id")


class UserProfileUpdate(UserProfileBase):
    profile_picture: Optional[str] = Field(default=None, max_length=255)
    bio: Optional[str] = Field(default=None, max_length=500)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    zip_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)


class UserProfile(UserProfileBase, table=True):
    """Database model for user profiles."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE")
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)

    # Relationship to User (one-to-one)
    user: Optional["User"] = Relationship(back_populates="profile", sa_relationship_kwargs={"uselist": False})


class UserProfilePublic(UserProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID


class UserProfilesPublic(SQLModel):
    data: list[UserProfilePublic]
    count: int