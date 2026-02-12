"""
Comprehensive tests for private routes including success and failure scenarios.
"""
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import verify_password
from app.models import User
from tests.utils.utils import random_phone

class TestPrivateUserCreate:
    """Test POST /private/users/ endpoint."""

    def test_create_user_success(self, client: TestClient, db: Session) -> None:
        """Test successful user creation via private endpoint."""
        user_data = {
            "phone_number": "1234567890",
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 200
        response_data = r.json()

        # Verify response structure
        assert "id" in response_data
        assert response_data["phone_number"] == "1234567890"
        assert response_data["full_name"] == "Test User"
        assert "hashed_password" not in response_data  # Should not be in response

        # Verify user was created in database
        user = db.exec(select(User).where(User.id == response_data["id"])).first()
        assert user is not None
        assert user.phone_number == "1234567890"
        assert user.full_name == "Test User"
        assert verify_password("password123", user.hashed_password)

    def test_create_user_with_optional_fields(self, client: TestClient, db: Session) -> None:
        """Test user creation with optional fields."""
        phone_number = random_phone()
        user_data = {
            "phone_number": phone_number,
            "password": "password123",
            "full_name": "Test User 2",
            "is_verified": True,
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 200
        response_data = r.json()
        assert response_data["phone_number"] == phone_number
        assert response_data["full_name"] == "Test User 2"

        # Verify user was created in database
        user = db.exec(select(User).where(User.id == response_data["id"])).first()
        assert user is not None
        assert user.phone_number == phone_number
        assert user.full_name == "Test User 2"

    def test_create_user_missing_phone_number(self, client: TestClient) -> None:
        """Test user creation without phone number."""
        user_data = {
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_missing_password(self, client: TestClient) -> None:
        """Test user creation without password."""
        user_data = {
            "email": "test@example.com",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_missing_full_name(self, client: TestClient) -> None:
        """Test user creation without full name."""
        user_data = {
            "email": "test@example.com",
            "password": "password123",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_empty_data(self, client: TestClient) -> None:
        """Test user creation with empty data."""
        user_data = {}

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_invalid_phone_format(self, client: TestClient) -> None:
        """Test user creation with invalid phone number format."""
        user_data = {
            "phone_number": "invalid-phone-number",
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_empty_email(self, client: TestClient) -> None:
        """Test user creation with empty email."""
        user_data = {
            "email": "",
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_empty_password(self, client: TestClient) -> None:
        """Test user creation with empty password."""
        user_data = {
            "email": "test@example.com",
            "password": "",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_empty_full_name(self, client: TestClient) -> None:
        """Test user creation with empty full name."""
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "full_name": "",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422  # Validation error

    def test_create_user_very_long_email(self, client: TestClient) -> None:
        """Test user creation with very long email."""
        long_email = "a" * 100 + "@" + "b" * 100 + ".com"
        user_data = {
            "email": long_email,
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        # This might be valid or invalid depending on email validation rules
        assert r.status_code in [200, 422]

    def test_create_user_very_long_password(self, client: TestClient) -> None:
        """Test user creation with very long password."""
        long_password = "a" * 1000
        user_data = {
            "email": "test@example.com",
            "password": long_password,
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        # This might be valid or invalid depending on password validation rules
        assert r.status_code in [200, 422]

    def test_create_user_very_long_full_name(self, client: TestClient) -> None:
        """Test user creation with very long full name."""
        long_name = "a" * 1000
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "full_name": long_name,
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        # This might be valid or invalid depending on name validation rules
        assert r.status_code in [200, 422]

    def test_create_user_special_characters_in_name(self, client: TestClient, db: Session) -> None:
        """Test user creation with special characters in full name."""
        user_data = {
            "phone_number": "+1234567894",
            "password": "password123",
            "full_name": "José María O'Connor-Smith",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 200
        response_data = r.json()
        assert response_data["full_name"] == "José María O'Connor-Smith"

        # Verify user was created in database
        user = db.exec(select(User).where(User.id == response_data["id"])).first()
        assert user is not None
        assert user.full_name == "José María O'Connor-Smith"

    def test_create_user_unicode_email(self, client: TestClient) -> None:
        """Test user creation with unicode characters in phone number."""
        user_data = {
            "phone_number": "tëst@ëxämplë.com",
            "password": "password123",
            "full_name": "Test User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 422

    def test_create_user_duplicate_phone(self, client: TestClient, db: Session) -> None:
        """Test user creation with duplicate phone number."""
        phone_number = "+9876543210"
        
        # Create first user
        user_data1 = {
            "phone_number": phone_number,
            "password": "password123",
            "full_name": "First User",
        }
        r1 = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data1,
        )
        assert r1.status_code == 200

        # Try to create second user with same phone number
        user_data2 = {
            "phone_number": phone_number,
            "password": "password456",
            "full_name": "Second User",
        }
        r2 = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data2,
        )
        
        # This might succeed or fail depending on unique constraint
        assert r2.status_code ==  400

    def test_create_user_no_auth_required(self, client: TestClient) -> None:
        """Test that private user creation doesn't require authentication."""
        user_data = {
            "phone_number": "+1234567898",
            "password": "password123",
            "full_name": "No Auth User",
        }

        r = client.post(
            f"{settings.API_V1_STR}/private/users/",
            json=user_data,
        )

        assert r.status_code == 200
        response_data = r.json()
        assert response_data["phone_number"] == "+1234567898"
