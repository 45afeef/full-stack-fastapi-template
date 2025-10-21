"""
Tests for agency endpoints (creation and staff assignment).
"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string


class TestAgencies:
    def test_create_agency_success(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(user.id),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 200
        created_agency = r.json()
        assert created_agency["agency_name"] == "ACME Travel Agency"
        assert created_agency["contact_email"] == "contact@acme.com"
        assert "id" in created_agency

    def test_create_agency_user_not_found(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "User not found for created_by"

    def test_create_agency_requires_superuser(self, client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=normal_user_token_headers,
            json=agency_data,
        )
        assert r.status_code == 403


    def test_create_agency_no_auth(self, client: TestClient) -> None:
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(f"{settings.API_V1_STR}/travel-agency", json=agency_data)
        assert r.status_code == 401


    def test_create_agency_missing_name(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test travel agency creation without required name field."""
        agency_data = {
            "contact_email": "contact@acme.com",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 422  # Validation error

    def test_create_agency_invalid_email(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test travel agency creation with invalid email format."""
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "invalid-email-format",
            "created_by": str(user.id),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 422  # Validation error


class TestAssignAgencyStaff:
    def test_assign_agency_staff_success(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        username1 = random_email()
        password1 = random_lower_string()
        user_in1 = UserCreate(email=username1, password=password1)
        user1 = crud.create_user(session=db, user_create=user_in1)

        username2 = random_email()
        password2 = random_lower_string()
        user_in2 = UserCreate(email=username2, password=password2)
        user2 = crud.create_user(session=db, user_create=user_in2)

        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(user1.id),
        }
        agency = crud.create_travel_agency(session=db, agency=agency_data)

        staff_data = {"user_id": str(user2.id), "role": "agent"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency.id}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 200
        created_staff = r.json()
        assert created_staff["user_id"] == str(user2.id)
        assert created_staff["role"] == "agent"
        assert "id" in created_staff

    def test_assign_agency_staff_agency_not_found(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        staff_data = {"user_id": str(user.id), "role": "agent"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Agency not found"

    def test_assign_agency_staff_requires_superuser(self, client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
        staff_data = {"user_id": str(uuid.uuid4()), "role": "agent"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=normal_user_token_headers,
            json=staff_data,
        )
        assert r.status_code == 403

    def test_assign_agency_staff_no_auth(self, client: TestClient) -> None:
        staff_data = {"user_id": str(uuid.uuid4()), "role": "agent"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            json=staff_data,
        )
        assert r.status_code == 401

    def test_assign_agency_staff_missing_user_id(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        staff_data = {"role": "agent"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 422
