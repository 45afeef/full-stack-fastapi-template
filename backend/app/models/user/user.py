from datetime import datetime
from typing import TYPE_CHECKING, Optional
import re
import uuid

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .profile import Profile
from sqlmodel import Column, DateTime, func

# Shared properties
class UserBase(SQLModel):
    phone_number: str = Field(unique=True, index=True, max_length=20)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number in E.164 format: +[1-9]d{1,14}"""
        if not v:
            raise ValueError("Phone number cannot be empty")
        
        # Remove any whitespace
        v = v.strip()
        
        # Check E.164 format: starts with +, followed by 1-15 digits, no leading zero after +
        if not re.match(r"^\+?[1-9]\d{1,14}$", v):
            raise ValueError(
                "Phone number must be in E.164 format (e.g., +1234567890). "
                "It should start with + followed by country code and number (1-15 digits total)."
            )
        
        return v


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    phone_number: str | None = Field(default=None, max_length=20)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=20)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

    
    profile: Optional["Profile"] = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})

# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None
    updated_at: datetime | None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
