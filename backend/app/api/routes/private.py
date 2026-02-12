import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.deps import SessionDep
from app import crud
from app.core.security import get_password_hash
from app.models import (
    User,
    UserPublic,
)

router = APIRouter(tags=["private"], prefix="/private")



class PrivateUserCreate(BaseModel):
    phone_number: str = Field(..., max_length=20)
    password: str = Field(min_length=8, max_length=40)
    full_name: str = Field(..., max_length=100)
    is_verified: bool = False

    @field_validator("full_name")
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty or only whitespace.")
        return v

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



@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user.
    """
    user = crud.get_user_by_phone(session=session, phone_number=user_in.phone_number)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this phone number already exists in the system.",
        )
    
    user = User(
        phone_number=user_in.phone_number,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    session.add(user)
    session.commit()

    return user
