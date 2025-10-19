"""
Comprehensive tests for login routes including success and failure scenarios.
"""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_password
from app.crud import create_user
from app.models import UserCreate
from app.utils import generate_password_reset_token
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


class TestLoginAccessToken:
    """Test POST /login/access-token endpoint."""

    def test_get_access_token_success(self, client: TestClient) -> None:
        """Test successful login with valid credentials."""
        login_data = {
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        tokens = r.json()
        assert r.status_code == 200
        assert "access_token" in tokens
        assert tokens["access_token"]
        assert isinstance(tokens["access_token"], str)

    def test_get_access_token_incorrect_password(self, client: TestClient) -> None:
        """Test login with incorrect password."""
        login_data = {
            "username": settings.FIRST_SUPERUSER,
            "password": "incorrect_password",
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 400
        assert r.json()["detail"] == "Incorrect email or password"

    def test_get_access_token_incorrect_email(self, client: TestClient) -> None:
        """Test login with non-existent email."""
        login_data = {
            "username": "nonexistent@example.com",
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 400
        assert r.json()["detail"] == "Incorrect email or password"

    def test_get_access_token_inactive_user(self, client: TestClient, db: Session) -> None:
        """Test login with inactive user."""
        email = random_email()
        password = random_lower_string()
        user_create = UserCreate(
            email=email,
            full_name="Test User",
            password=password,
            is_active=False,  # Inactive user
            is_superuser=False,
        )
        create_user(session=db, user_create=user_create)
        
        login_data = {
            "username": email,
            "password": password,
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 400
        assert r.json()["detail"] == "Inactive user"

    def test_get_access_token_missing_username(self, client: TestClient) -> None:
        """Test login with missing username."""
        login_data = {
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 422  # Validation error

    def test_get_access_token_missing_password(self, client: TestClient) -> None:
        """Test login with missing password."""
        login_data = {
            "username": settings.FIRST_SUPERUSER,
        }
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 422  # Validation error

    def test_get_access_token_empty_credentials(self, client: TestClient) -> None:
        """Test login with empty credentials."""
        login_data = {}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 422  # Validation error


class TestLoginTestToken:
    """Test POST /login/test-token endpoint."""

    def test_use_access_token_success(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test successful token validation."""
        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=superuser_token_headers,
        )
        result = r.json()
        assert r.status_code == 200
        assert "email" in result
        assert "id" in result
        assert "is_active" in result
        assert "is_superuser" in result
        assert result["email"] == settings.FIRST_SUPERUSER
        assert result["is_superuser"] is True

    def test_use_access_token_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test token validation for normal user."""
        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=normal_user_token_headers,
        )
        result = r.json()
        assert r.status_code == 200
        assert result["email"] == settings.EMAIL_TEST_USER
        assert result["is_superuser"] is False

    def test_use_access_token_invalid_token(self, client: TestClient) -> None:
        """Test token validation with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=headers,
        )
        
        assert r.status_code in (401, 403)

    def test_use_access_token_missing_token(self, client: TestClient) -> None:
        """Test token validation without token."""
        r = client.post(f"{settings.API_V1_STR}/login/test-token")
        assert r.status_code == 401

    def test_use_access_token_malformed_header(self, client: TestClient) -> None:
        """Test token validation with malformed authorization header."""
        headers = {"Authorization": "InvalidFormat token"}
        r = client.post(
            f"{settings.API_V1_STR}/login/test-token",
            headers=headers,
        )
        assert r.status_code == 401


class TestPasswordRecovery:
    """Test POST /password-recovery/{email} endpoint."""

    def test_recovery_password_success(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test successful password recovery email."""
        with (
            patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
            patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
        ):
            email = "test@example.com"
            r = client.post(
                f"{settings.API_V1_STR}/password-recovery/{email}",
                headers=normal_user_token_headers,
            )
            assert r.status_code == 200
            assert r.json() == {"message": "Password recovery email sent"}

    def test_recovery_password_user_not_exists(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test password recovery for non-existent user."""
        email = "nonexistent@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{email}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "The user with this email does not exist in the system."

    def test_recovery_password_invalid_email_format(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test password recovery with invalid email format."""
        email = "invalid-email-format"
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{email}",
            headers=normal_user_token_headers,
        )
        # This might return 404 or 422 depending on validation
        assert r.status_code in [404, 422]

    def test_recovery_password_empty_email(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test password recovery with empty email."""
        email = ""
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{email}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 404


class TestResetPassword:
    """Test POST /reset-password/ endpoint."""

    def test_reset_password_success(self, client: TestClient, db: Session) -> None:
        """Test successful password reset."""
        email = random_email()
        password = random_lower_string()
        new_password = random_lower_string()

        user_create = UserCreate(
            email=email,
            full_name="Test User",
            password=password,
            is_active=True,
            is_superuser=False,
        )
        user = create_user(session=db, user_create=user_create)
        token = generate_password_reset_token(email=email)
        headers = user_authentication_headers(client=client, email=email, password=password)
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
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test password reset with invalid token."""
        data = {"new_password": "newpassword123", "token": "invalid_token"}
        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            headers=superuser_token_headers,
            json=data,
        )
        response = r.json()
        assert r.status_code == 400
        assert response["detail"] == "Invalid token"

    def test_reset_password_user_not_found(self, client: TestClient, db: Session) -> None:
        """Test password reset for non-existent user."""
        email = "nonexistent@example.com"
        token = generate_password_reset_token(email=email)
        data = {"new_password": "newpassword123", "token": token}
        
        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json=data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "The user with this email does not exist in the system."

    def test_reset_password_inactive_user(self, client: TestClient, db: Session) -> None:
        """Test password reset for inactive user."""
        email = random_email()
        password = random_lower_string()
        new_password = random_lower_string()

        user_create = UserCreate(
            email=email,
            full_name="Test User",
            password=password,
            is_active=False,  # Inactive user
            is_superuser=False,
        )
        create_user(session=db, user_create=user_create)
        token = generate_password_reset_token(email=email)
        data = {"new_password": new_password, "token": token}

        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json=data,
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "Inactive user"

    def test_reset_password_missing_token(self, client: TestClient) -> None:
        """Test password reset without token."""
        data = {"new_password": "newpassword123"}
        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json=data,
        )
        assert r.status_code == 422  # Validation error

    def test_reset_password_missing_new_password(self, client: TestClient) -> None:
        """Test password reset without new password."""
        data = {"token": "some_token"}
        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json=data,
        )
        assert r.status_code == 422  # Validation error

    def test_reset_password_empty_data(self, client: TestClient) -> None:
        """Test password reset with empty data."""
        data = {}
        r = client.post(
            f"{settings.API_V1_STR}/reset-password/",
            json=data,
        )
        assert r.status_code == 422  # Validation error


class TestPasswordRecoveryHtmlContent:
    """Test POST /password-recovery-html-content/{email} endpoint (Admin only)."""

    def test_recovery_password_html_content_success(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test successful HTML content generation for password recovery."""
        email = settings.EMAIL_TEST_USER
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery-html-content/{email}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_recovery_password_html_content_user_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test HTML content generation for non-existent user."""
        email = "nonexistent@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery-html-content/{email}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "The user with this username does not exist in the system."

    def test_recovery_password_html_content_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that HTML content generation requires superuser privileges."""
        email = settings.EMAIL_TEST_USER
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery-html-content/{email}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403

    def test_recovery_password_html_content_no_auth(self, client: TestClient) -> None:
        """Test HTML content generation without authentication."""
        email = settings.EMAIL_TEST_USER
        r = client.post(f"{settings.API_V1_STR}/password-recovery-html-content/{email}")
        assert r.status_code == 401
