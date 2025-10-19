"""
Comprehensive tests for user routes including success and failure scenarios.
"""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.security import verify_password
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string


class TestUserList:
    """Test GET /users/ endpoint."""

    def test_get_users_superuser_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful user listing by superuser."""
        # Create some test users
        for i in range(3):
            username = random_email()
            password = random_lower_string()
            user_in = UserCreate(email=username, password=password)
            crud.create_user(session=db, user_create=user_in)

        r = client.get(f"{settings.API_V1_STR}/users/", headers=superuser_token_headers)
        all_users = r.json()

        assert r.status_code == 200
        assert "data" in all_users
        assert "count" in all_users
        assert isinstance(all_users["data"], list)
        assert isinstance(all_users["count"], int)
        assert len(all_users["data"]) >= 3  # At least the users we created

    def test_get_users_with_pagination(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test user listing with pagination."""
        # Create test users
        for i in range(5):
            username = random_email()
            password = random_lower_string()
            user_in = UserCreate(email=username, password=password)
            crud.create_user(session=db, user_create=user_in)

        r = client.get(
            f"{settings.API_V1_STR}/users/?skip=0&limit=2",
            headers=superuser_token_headers,
        )
        all_users = r.json()

        assert r.status_code == 200
        assert len(all_users["data"]) <= 2

    def test_get_users_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that user listing requires superuser privileges."""
        r = client.get(f"{settings.API_V1_STR}/users/", headers=normal_user_token_headers)
        assert r.status_code == 403

    def test_get_users_no_auth(self, client: TestClient) -> None:
        """Test user listing without authentication."""
        r = client.get(f"{settings.API_V1_STR}/users/")
        assert r.status_code == 401


class TestUserCreate:
    """Test POST /users/ endpoint."""

    def test_create_user_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful user creation by superuser."""
        with (
            patch("app.utils.send_email", return_value=None),
            patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
            patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
        ):
            username = random_email()
            password = random_lower_string()
            data = {"email": username, "password": password}
            r = client.post(
                f"{settings.API_V1_STR}/users/",
                headers=superuser_token_headers,
                json=data,
            )
            assert 200 <= r.status_code < 300
            created_user = r.json()
            user = crud.get_user_by_email(session=db, email=username)
            assert user
            assert user.email == created_user["email"]

    def test_create_user_existing_email(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test user creation with existing email."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        crud.create_user(session=db, user_create=user_in)
        
        data = {"email": username, "password": password}
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "The user with this email already exists in the system."

    def test_create_user_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that user creation requires superuser privileges."""
        username = random_email()
        password = random_lower_string()
        data = {"email": username, "password": password}
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=normal_user_token_headers,
            json=data,
        )
        assert r.status_code == 403

    def test_create_user_no_auth(self, client: TestClient) -> None:
        """Test user creation without authentication."""
        username = random_email()
        password = random_lower_string()
        data = {"email": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/users/", json=data)
        assert r.status_code == 401

    def test_create_user_missing_email(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test user creation without email."""
        data = {"password": "password123"}
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 422  # Validation error

    def test_create_user_missing_password(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test user creation without password."""
        data = {"email": "test@example.com"}
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 422  # Validation error

    def test_create_user_invalid_email_format(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test user creation with invalid email format."""
        data = {"email": "invalid-email", "password": "password123"}
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 422  # Validation error


class TestUserMe:
    """Test GET /users/me endpoint."""

    def test_get_user_me_superuser(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test getting current superuser info."""
        r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
        current_user = r.json()
        assert r.status_code == 200
        assert current_user["is_active"] is True
        assert current_user["is_superuser"] is True
        assert current_user["email"] == settings.FIRST_SUPERUSER

    def test_get_user_me_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test getting current normal user info."""
        r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
        current_user = r.json()
        assert r.status_code == 200
        assert current_user["is_active"] is True
        assert current_user["is_superuser"] is False
        assert current_user["email"] == settings.EMAIL_TEST_USER

    def test_get_user_me_no_auth(self, client: TestClient) -> None:
        """Test getting current user without authentication."""
        r = client.get(f"{settings.API_V1_STR}/users/me")
        assert r.status_code == 401


class TestUserUpdateMe:
    """Test PATCH /users/me endpoint."""

    def test_update_user_me_success(
        self, client: TestClient, normal_user_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful user profile update."""
        full_name = "Updated Name"
        email = random_email()
        data = {"full_name": full_name, "email": email}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me",
            headers=normal_user_token_headers,
            json=data,
        )
        assert r.status_code == 200
        updated_user = r.json()
        assert updated_user["email"] == email
        assert updated_user["full_name"] == full_name

        user_query = select(User).where(User.email == email)
        user_db = db.exec(user_query).first()
        assert user_db
        assert user_db.email == email
        assert user_db.full_name == full_name

    def test_update_user_me_email_exists(
        self, client: TestClient, normal_user_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test user profile update with existing email."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        data = {"email": user.email}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me",
            headers=normal_user_token_headers,
            json=data,
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "User with this email already exists"

    def test_update_user_me_no_auth(self, client: TestClient) -> None:
        """Test user profile update without authentication."""
        data = {"full_name": "New Name"}
        r = client.patch(f"{settings.API_V1_STR}/users/me", json=data)
        assert r.status_code == 401

    def test_update_user_me_partial_update(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test partial user profile update."""
        data = {"full_name": "Partial Update"}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me",
            headers=normal_user_token_headers,
            json=data,
        )
        assert r.status_code == 200
        updated_user = r.json()
        assert updated_user["full_name"] == "Partial Update"


class TestUserUpdatePasswordMe:
    """Test PATCH /users/me/password endpoint."""

    def test_update_password_me_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful password update."""
        new_password = random_lower_string()
        data = {
            "current_password": settings.FIRST_SUPERUSER_PASSWORD,
            "new_password": new_password,
        }
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 200
        updated_user = r.json()
        assert updated_user["message"] == "Password updated successfully"

        user_query = select(User).where(User.email == settings.FIRST_SUPERUSER)
        user_db = db.exec(user_query).first()
        assert user_db
        assert verify_password(new_password, user_db.hashed_password)

        # Revert to the old password to keep consistency in test
        old_data = {
            "current_password": new_password,
            "new_password": settings.FIRST_SUPERUSER_PASSWORD,
        }
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=old_data,
        )
        db.refresh(user_db)
        assert r.status_code == 200
        assert verify_password(settings.FIRST_SUPERUSER_PASSWORD, user_db.hashed_password)

    def test_update_password_me_incorrect_current_password(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test password update with incorrect current password."""
        new_password = random_lower_string()
        data = {"current_password": "wrong_password", "new_password": new_password}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 400
        updated_user = r.json()
        assert updated_user["detail"] == "Incorrect password"

    def test_update_password_me_same_password(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test password update with same password."""
        data = {
            "current_password": settings.FIRST_SUPERUSER_PASSWORD,
            "new_password": settings.FIRST_SUPERUSER_PASSWORD,
        }
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 400
        updated_user = r.json()
        assert updated_user["detail"] == "New password cannot be the same as the current one"

    def test_update_password_me_no_auth(self, client: TestClient) -> None:
        """Test password update without authentication."""
        data = {
            "current_password": "old_password",
            "new_password": "new_password",
        }
        r = client.patch(f"{settings.API_V1_STR}/users/me/password", json=data)
        assert r.status_code == 401

    def test_update_password_me_missing_current_password(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test password update without current password."""
        data = {"new_password": "new_password"}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 422  # Validation error

    def test_update_password_me_missing_new_password(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test password update without new password."""
        data = {"current_password": settings.FIRST_SUPERUSER_PASSWORD}
        r = client.patch(
            f"{settings.API_V1_STR}/users/me/password",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 422  # Validation error


class TestUserDeleteMe:
    """Test DELETE /users/me endpoint."""

    def test_delete_user_me_success(self, client: TestClient, db: Session) -> None:
        """Test successful user self-deletion."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)
        user_id = user.id

        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        tokens = r.json()
        a_token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {a_token}"}

        r = client.delete(f"{settings.API_V1_STR}/users/me", headers=headers)
        assert r.status_code == 200
        deleted_user = r.json()
        assert deleted_user["message"] == "User deleted successfully"
        result = db.exec(select(User).where(User.id == user_id)).first()
        assert result is None

    def test_delete_user_me_as_superuser(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test that superusers cannot delete themselves."""
        r = client.delete(
            f"{settings.API_V1_STR}/users/me",
            headers=superuser_token_headers,
        )
        assert r.status_code == 403
        response = r.json()
        assert response["detail"] == "Super users are not allowed to delete themselves"

    def test_delete_user_me_no_auth(self, client: TestClient) -> None:
        """Test user self-deletion without authentication."""
        r = client.delete(f"{settings.API_V1_STR}/users/me")
        assert r.status_code == 401


class TestUserSignup:
    """Test POST /users/signup endpoint."""

    def test_register_user_success(self, client: TestClient, db: Session) -> None:
        """Test successful user registration."""
        username = random_email()
        password = random_lower_string()
        full_name = random_lower_string()
        data = {"email": username, "password": password, "full_name": full_name}
        r = client.post(f"{settings.API_V1_STR}/users/signup", json=data)
        assert r.status_code == 200
        created_user = r.json()
        assert created_user["email"] == username
        assert created_user["full_name"] == full_name

        user_query = select(User).where(User.email == username)
        user_db = db.exec(user_query).first()
        assert user_db
        assert user_db.email == username
        assert user_db.full_name == full_name
        assert verify_password(password, user_db.hashed_password)

    def test_register_user_already_exists(self, client: TestClient) -> None:
        """Test user registration with existing email."""
        password = random_lower_string()
        full_name = random_lower_string()
        data = {
            "email": settings.FIRST_SUPERUSER,
            "password": password,
            "full_name": full_name,
        }
        r = client.post(f"{settings.API_V1_STR}/users/signup", json=data)
        assert r.status_code == 400
        assert r.json()["detail"] == "The user with this email already exists in the system"

    def test_register_user_missing_email(self, client: TestClient) -> None:
        """Test user registration without email."""
        data = {"password": "password123", "full_name": "Test User"}
        r = client.post(f"{settings.API_V1_STR}/users/signup", json=data)
        assert r.status_code == 422  # Validation error

    def test_register_user_missing_password(self, client: TestClient) -> None:
        """Test user registration without password."""
        data = {"email": "test@example.com", "full_name": "Test User"}
        r = client.post(f"{settings.API_V1_STR}/users/signup", json=data)
        assert r.status_code == 422  # Validation error

    def test_register_user_missing_full_name(self, client: TestClient) -> None:
        """Test user registration without full name."""
        data = {"email": "test@example.com", "password": "password123"}
        r = client.post(f"{settings.API_V1_STR}/users/signup", json=data)
        assert r.status_code == 422  # Validation error


class TestUserGetById:
    """Test GET /users/{user_id} endpoint."""

    def test_get_existing_user_superuser(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test getting user by ID as superuser."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)
        user_id = user.id
        
        r = client.get(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=superuser_token_headers,
        )
        assert 200 <= r.status_code < 300
        api_user = r.json()
        existing_user = crud.get_user_by_email(session=db, email=username)
        assert existing_user
        assert existing_user.email == api_user["email"]

    def test_get_existing_user_current_user(self, client: TestClient, db: Session) -> None:
        """Test getting own user by ID."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)
        user_id = user.id

        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        tokens = r.json()
        a_token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {a_token}"}

        r = client.get(f"{settings.API_V1_STR}/users/{user_id}", headers=headers)
        assert 200 <= r.status_code < 300
        api_user = r.json()
        existing_user = crud.get_user_by_email(session=db, email=username)
        assert existing_user
        assert existing_user.email == api_user["email"]

    def test_get_existing_user_permissions_error(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test getting user by ID without sufficient privileges."""
        r = client.get(
            f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "The user doesn't have enough privileges"

    def test_get_user_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test getting non-existent user by ID."""
        non_existent_id = uuid.uuid4()
        r = client.get(
            f"{settings.API_V1_STR}/users/{non_existent_id}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 404

    def test_get_user_no_auth(self, client: TestClient) -> None:
        """Test getting user by ID without authentication."""
        r = client.get(f"{settings.API_V1_STR}/users/{uuid.uuid4()}")
        assert r.status_code == 401


class TestUserUpdate:
    """Test PATCH /users/{user_id} endpoint."""

    def test_update_user_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful user update by superuser."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        data = {"full_name": "Updated_full_name"}
        r = client.patch(
            f"{settings.API_V1_STR}/users/{user.id}",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 200
        updated_user = r.json()
        assert updated_user["full_name"] == "Updated_full_name"

        user_query = select(User).where(User.email == username)
        user_db = db.exec(user_query).first()
        db.refresh(user_db)
        assert user_db
        assert user_db.full_name == "Updated_full_name"

    def test_update_user_not_exists(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test updating non-existent user."""
        data = {"full_name": "Updated_full_name"}
        r = client.patch(
            f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "The user with this id does not exist in the system"

    def test_update_user_email_exists(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test updating user with existing email."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        username2 = random_email()
        password2 = random_lower_string()
        user_in2 = UserCreate(email=username2, password=password2)
        user2 = crud.create_user(session=db, user_create=user_in2)

        data = {"email": user2.email}
        r = client.patch(
            f"{settings.API_V1_STR}/users/{user.id}",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "User with this email already exists"

    def test_update_user_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that user update requires superuser privileges."""
        data = {"full_name": "Updated Name"}
        r = client.patch(
            f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
            headers=normal_user_token_headers,
            json=data,
        )
        assert r.status_code == 403

    def test_update_user_no_auth(self, client: TestClient) -> None:
        """Test user update without authentication."""
        data = {"full_name": "Updated Name"}
        r = client.patch(f"{settings.API_V1_STR}/users/{uuid.uuid4()}", json=data)
        assert r.status_code == 401


class TestUserDelete:
    """Test DELETE /users/{user_id} endpoint."""

    def test_delete_user_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful user deletion by superuser."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)
        user_id = user.id
        
        r = client.delete(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        deleted_user = r.json()
        assert deleted_user["message"] == "User deleted successfully"
        result = db.exec(select(User).where(User.id == user_id)).first()
        assert result is None

    def test_delete_user_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test deleting non-existent user."""
        r = client.delete(
            f"{settings.API_V1_STR}/users/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "User not found"

    def test_delete_user_current_super_user_error(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test that superusers cannot delete themselves."""
        super_user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
        assert super_user
        user_id = super_user.id

        r = client.delete(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Super users are not allowed to delete themselves"

    def test_delete_user_without_privileges(
        self, client: TestClient, normal_user_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test user deletion without sufficient privileges."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        r = client.delete(
            f"{settings.API_V1_STR}/users/{user.id}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "The user doesn't have enough privileges"

    def test_delete_user_no_auth(self, client: TestClient) -> None:
        """Test user deletion without authentication."""
        r = client.delete(f"{settings.API_V1_STR}/users/{uuid.uuid4()}")
        assert r.status_code == 401
