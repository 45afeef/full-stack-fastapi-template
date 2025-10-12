from typing import Optional
import uuid

from sqlmodel import Field, SQLModel


# Shared properties
class PhoneNumberBase(SQLModel):
    number: str = Field(unique=True, index=True, max_length=20)
    is_verified: bool = Field(default=False)
    type: Optional[str] = Field(default=None, max_length=50)
    more_info: Optional[str] = Field(default=None, max_length=255)
    owner_type: Optional[str] = Field(default="profile", max_length=50)  # e.g., 'profile','provider','agency'
    owner_id: Optional[uuid.UUID] = Field(default=None)


class PhoneNumberCreate(PhoneNumberBase):
    pass


class PhoneNumberUpdate(SQLModel):
    number: Optional[str] = Field(default=None, max_length=20)
    is_verified: Optional[bool] = None
    type: Optional[str] = None
    more_info: Optional[str] = None
    owner_type: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None


class PhoneNumber(PhoneNumberBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: Optional[str] = Field(default=None)


class PhoneNumberPublic(PhoneNumberBase):
    id: uuid.UUID


class PhoneNumbersPublic(SQLModel):
    data: list[PhoneNumberPublic]
    count: int