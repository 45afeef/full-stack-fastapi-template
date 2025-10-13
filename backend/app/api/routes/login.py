from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post(
    "/login/access-token",
    response_model=Token,
    summary="Obtain an access token (OAuth2 password flow)",
    description=(
        "Authenticate a user using the OAuth2 password flow and return a short-lived "
        "access token. Use this token in the Authorization header as: `Authorization: Bearer <token>` "
        "for subsequent authenticated requests."
    ),
)
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    Obtain an access token for a user.

    This endpoint implements the OAuth2 "password" grant type commonly used by first-party applications.

    Detailed behavior:
    - Accepts form-encoded fields `username` (user email) and `password` as required by
      `OAuth2PasswordRequestForm`.
    - Verifies credentials via `crud.authenticate`.
    - If valid and the user is active, creates a JWT access token with an expiration defined
      by `settings.ACCESS_TOKEN_EXPIRE_MINUTES`.

    Typical usage order:
    1. The client calls this endpoint with user credentials.
    2. The API responds with a JSON object containing `access_token`.
    3. The client stores the token (in memory, secure cookie or mobile secure storage) and
       includes it on subsequent requests in the `Authorization` header.

    Security notes:
    - This endpoint should be served over HTTPS in production to protect credentials.
    - Access tokens are short-lived. For refresh workflows, implement a refresh-token endpoint
      (not provided here) or use another strategy.

    Responses:
    - 200: Returns a `Token` object: {"access_token": "<token>"}
    - 400: Wrong credentials or inactive user. Returns an error detail message.

    Example (curl):
    curl -X POST ".../login/access-token" -d "username=user@example.com&password=secret"
    """
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post(
    "/login/test-token",
    response_model=UserPublic,
    summary="Validate an access token and return current user",
    description=(
        "Validate the provided Bearer access token and return the public representation of the "
        "current user. This is useful for clients to verify that a token is still valid and to fetch "
        "the currently authenticated user's basic info."
    ),
)
def test_token(current_user: CurrentUser) -> Any:
    """
    Validate a token and return the current user.

    - Requires an `Authorization: Bearer <token>` header.
    - Returns the `UserPublic` model for the authenticated user when the token is valid.

    Responses:
    - 200: Returns the public user fields.
    - 401: If token is missing/invalid (handled by dependency).
    """
    return current_user


@router.post(
    "/password-recovery/{email}",
    response_model=Message,
    summary="Send password recovery email",
    description=(
        "Trigger a password recovery email to the provided email address if a user exists. "
        "The email includes a one-time token the user can use to reset their password."
    ),
)
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Start the password recovery flow.

    Behavior / notes:
    - The endpoint looks up the user by email. If the user exists, it generates a secure,
      time-limited password reset token using `generate_password_reset_token`.
    - It builds an email (HTML) via `generate_reset_password_email` and sends it with
      `send_email`.
    - The endpoint intentionally does not leak whether the email exists beyond a 404 to
      keep the behavior explicit. You can change to a generic success response for improved
      privacy if desired.

    Responses:
    - 200: Message that an email was sent.
    - 404: Email address not found in the system.

    Example usage sequence:
    1. Client POSTs to `/password-recovery/user@example.com`.
    2. Server emails a reset link containing the token.
    3. Client follows link to a web page which collects the new password and calls `/reset-password/`.
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Password recovery email sent")


@router.post(
    "/reset-password/",
    response_model=Message,
    summary="Reset a user's password using a recovery token",
    description=(
        "Reset a password using the token previously sent by the password recovery flow. "
        "The request body must include `token` and `new_password` fields."
    ),
)
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Complete password reset.

    Steps:
    1. Client obtains a token via the password recovery email.
    2. Client POSTs JSON {"token": "<token>", "new_password": "newpass"} to this endpoint.
    3. Server verifies token, looks up the user, updates and hashes the password, and persists it.

    Responses:
    - 200: Password updated successfully.
    - 400: Invalid token or inactive user.
    - 404: No user found for the token's email.
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
    summary="(Admin) Preview password recovery HTML email",
    description=(
        "Admin-only endpoint that generates and returns the HTML body for a password recovery email. "
        "Helpful for debugging email templates without actually sending emails. This endpoint is protected "
        "by `get_current_active_superuser` and should only be used in staging or development."
    ),
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    Return HTML content for the password recovery email (admin/debug).

    - Protected: only accessible to active superusers via dependency.
    - Generates a fresh token and returns the rendered HTML and subject in the response headers.

    Responses:
    - 200: HTML body of the recovery email.
    - 404: If user not found.
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
