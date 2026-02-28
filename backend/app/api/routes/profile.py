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


# TODO : Found an Internal Server Error when there is no profile in the database
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
def create_profile(
    *,
    session: SessionDep,
    profile_in: ProfileCreate,
    current_user: CurrentUser = [Depends(get_current_user)],
) -> Any:
    """
    Create new profile.
    """

    # ensure that any provided unique contact information doesn't already exist
    # anywhere in the system. we need to check across all unique columns because
    # a value placed in a primary field should not later be reused as a
    # secondary, and vice versa. if a conflict is found respond with 409.
    unique_fields = [
        "primary_phone_number",
        "secondary_phone_number",
        "primary_email",
        "secondary_email",
    ]

    # collect the values that were supplied by the client
    provided: dict[str, str] = {}
    for field in unique_fields:
        val = getattr(profile_in, field)
        if val is not None:
            provided[field] = val

    if provided:
        # build a single query that looks for any of the provided values in any
        # of the unique columns. this avoids making N² queries and ensures we
        # catch cross-field collisions.
        from sqlalchemy import or_

        clauses: list[Any] = []
        for val in provided.values():
            for check in unique_fields:
                clauses.append(getattr(Profile, check) == val)

        statement = select(Profile).where(or_(*clauses))
        existing = session.exec(statement).first()
        if existing:
            # determine which input field caused the conflict for a helpful error
            # message. prefer reporting the field name from the request, not the
            # column where the value was found.
            for field, val in provided.items():
                # if the existing model has the value in any column we flagged it
                if any(getattr(existing, f) == val for f in unique_fields):
                    raise HTTPException(
                        status_code=409,
                        detail=f"Profile with this {field} already exists",
                    )
            # fallback generic message (shouldn't happen)
            raise HTTPException(
                status_code=409,
                detail="Profile with provided contact information already exists",
            )

    new_db_profile = Profile.model_validate(profile_in)
    # attach creator information if missing
    new_db_profile.created_by_user_id = new_db_profile.created_by_user_id or current_user.id

    session.add(new_db_profile)
    try:
        session.commit()
    except Exception as exc:  # pragma: no cover - guards against rare race conditions
        # translate unique constraint failure into a client-friendly error
        from sqlalchemy.exc import IntegrityError

        if isinstance(exc, IntegrityError):
            raise HTTPException(
                status_code=409, detail="Profile with provided contact information already exists"
            )
        raise
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
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # ensure the current user created it
    if profile.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")
    
    profile_data = profile_in.model_dump(exclude_unset=True)
    profile.sqlmodel_update(profile_data)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile

