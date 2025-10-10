from typing import Optional
import uuid

from sqlmodel import Field, Relationship, SQLModel  

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .person import Person

# Shared properties
class PhoneNumberBase(SQLModel):
    """
    PhoneNumber model to store phone numbers associated with individuals.
    This class is used to store phone numbers that can be linked to persons in the system.
    """
    number: str = Field(unique=True, index=True, max_length=20)
    type: str | None = Field(default=None, max_length=50)  # e.g., mobile, home, work
    person_id: Optional[uuid.UUID] = Field(default=None, foreign_key="person.id")


class PhoneNumberCreate(PhoneNumberBase):
    pass
    # No additional fields required for creation


class PhoneNumberUpdate(PhoneNumberBase):
    number: str | None = Field(default=None, max_length=20)
    type: str | None = Field(default=None, max_length=50)
    person_id: Optional[uuid.UUID] = Field(default=None, foreign_key="person.id")


class PhoneNumber(PhoneNumberBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: Optional[str] = Field(default=None)
    person: Optional["Person"] = Relationship(back_populates="phone")


class PhoneNumberPublic(PhoneNumberBase):
    id: uuid.UUID


class PhoneNumbersPublic(SQLModel):
    data: list[PhoneNumberPublic]
    count: int