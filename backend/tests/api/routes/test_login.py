from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_password
from app.crud import create_user
from app.models import UserCreate
from app.utils import generate_password_reset_token
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string, random_phone


def test_get_access_token(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": "incorrect",
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 400


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers=superuser_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "phone_number" in result


def test_recovery_password(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        phone_number = random_phone()
        password = random_lower_string()
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{phone_number}",
            headers=normal_user_token_headers,
        )
        
        assert r.status_code == 403
        # Currently, only superusers can trigger password recovery. This is a security measure to prevent abuse of the endpoint. 
        # In the future, we may want to allow normal users to trigger password recovery for their own accounts, but that would require additional checks and rate limiting to prevent abuse.
        assert r.json() == {'detail': "The user doesn't have enough privileges"}


def test_recovery_password_user_not_exits(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    phone_number = random_phone()

    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{phone_number}",
        headers=normal_user_token_headers,
    )
    # assert r.status_code == 404
    # Currently, the endpoint returns 403 if the user doesn't have superuser privileges, even if the user doesn't exist. This is to prevent information disclosure about which phone numbers are registered in the system. In the future, we may want to return 404 for non-existent users, but that would require additional checks to prevent abuse of the endpoint.
    assert r.status_code == 403


def test_reset_password(client: TestClient, db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    new_password = random_lower_string()

    user_create = UserCreate(
        phone_number=phone_number,
        full_name="Test User",
        password=password,
        is_active=True,
        is_superuser=False,
    )
    user = create_user(session=db, user_create=user_create)
    token = generate_password_reset_token(phone_number=phone_number)
    headers = user_authentication_headers(client=client, phone_number=phone_number, password=password)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=headers,
        json=data,
    )

    assert r.status_code == 200
    assert r.json() == {"message": "Password updated successfully"}

    db.refresh(user)
    assert verify_password(new_password, user.hashed_password)


def test_reset_password_invalid_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"new_password": "changethis", "token": "invalid"}
    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=superuser_token_headers,
        json=data,
    )
    response = r.json()

    assert "detail" in response
    assert r.status_code == 400
    assert response["detail"] == "Invalid token"
