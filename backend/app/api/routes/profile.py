import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from sqlmodel import func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_user,
)
from app.models.user.profile import Profile, ProfileCreate, ProfilePublic, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfilePublic,
)
def read_profiles(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve profiles.
    """

    count_statement = select(func.count()).select_from(Profile)
    count = session.exec(count_statement).one()

    statement = select(Profile).offset(skip).limit(limit)
    profiles = session.exec(statement).all()

    return ProfilePublic(data=profiles, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_user)], response_model=ProfilePublic
)
def create_profile(*, session: SessionDep, profile_in: ProfileCreate) -> Any:
    """
    Create new profile.
    """

    # Check for existing profile with same email if email is provided, or primary_phone_number and created_by current user

    new_db_profile = Profile.model_validate(profile_in)
    session.add(new_db_profile)
    session.commit()
    session.refresh(new_db_profile)

    return new_db_profile

# update the profile only if the created_by_user_id matches the current user id
@router.put("/{profile_id}", response_model=Profile)
def update_profile_by_id(
    profile_id: uuid.UUID,
    profile_in: ProfileUpdate,
    session: SessionDep,
    current_user: CurrentUser = [Depends(get_current_user)],
) -> Any:
    """
    Update a profile by ID if created by current user.
    """
    if profile.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile_data = profile_in.model_dump(exclude_unset=True)
    profile.sqlmodel_update(profile_data)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile

