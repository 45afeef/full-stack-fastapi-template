from  typing import TYPE_CHECKING, Optional
import uuid

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    # Ensure PhoneNumber is imported for relationship 
    from .phonenumber import PhoneNumber


# Shared properties
class PersonBase(SQLModel):
    """
    Person model to store most simple information about an individual.
    This class is used to store peoples once intract with the system or once mentioned in any record.
    so it can be reused in future without the need to re-enter the same information again and again.
    This is not a user model, this is just a person model.
    """
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    day_of_birth: Optional[int] = Field(default=None, ge=1, le=31)
    month_of_birth: Optional[int] = Field(default=None, ge=1, le=12)
    year_of_birth: Optional[int] = Field(default=None, ge=1900, le=2100)


# Properties to receive via API on creation
class PersonCreate(PersonBase):
    pass
    # No additional fields required for creation


# Properties to receive via API on update, all are optional
class PersonUpdate(PersonBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    phone: str | None = Field(default=None, max_length=20)
    full_name: str | None = Field(default=None, max_length=255)
    day_of_birth: Optional[int] = Field(default=None, ge=1, le=31)
    month_of_birth: Optional[int] = Field(default=None, ge=1, le=12)
    year_of_birth: Optional[int] = Field(default=None, ge=1900, le=2100)


# Database model, database table inferred from class name
class Person(PersonBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: Optional[str] = Field(default=None)
    phone: Optional[list["PhoneNumber"]] = Relationship(back_populates="person")


# Properties to return via API, id is always required
class PersonPublic(PersonBase):
    id: uuid.UUID

class PersonsPublic(SQLModel):
    data: list[PersonPublic]
    count: int