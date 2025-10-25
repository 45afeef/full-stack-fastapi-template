"""
Comprehensive tests for stays routes including success and failure scenarios.
"""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models.travel.enums import ServiceProviderType
from app.models import User, UserCreate
from app.models.travel.providers import ServiceProvider
from app.models.travel.stay import StayUnit
from tests.utils.utils import random_email, random_lower_string


class TestCreateStayProvider:
    """Test POST /stays/providers endpoint."""

    def test_create_stay_provider_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful stay provider creation."""
        # Create a user to be the owner and creator
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Test Hotel",
            "owner_id": str(user.id),
            "created_by": str(user.id),
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers",
            headers=superuser_token_headers,
            json=provider_data,
        )
        assert r.status_code == 201
        created_provider = r.json()
        assert created_provider["provider_name"] == "Test Hotel"
        assert created_provider["provider_type"] == "STAY"
        assert "id" in created_provider

    def test_create_stay_provider_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that stay provider creation requires superuser privileges."""
        provider_data = {
            "provider_type": "hotel",
            "provider_name": "Test Hotel",
            "owner_id": str(uuid.uuid4()),
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers",
            headers=normal_user_token_headers,
            json=provider_data,
        )
        assert r.status_code == 403

    def test_create_stay_provider_no_auth(self, client: TestClient) -> None:
        """Test stay provider creation without authentication."""
        provider_data = {
            "provider_type": "hotel",
            "provider_name": "Test Hotel",
            "owner_id": str(uuid.uuid4()),
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(f"{settings.API_V1_STR}/providers", json=provider_data)
        assert r.status_code == 401

    def test_create_stay_provider_missing_fields(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay provider creation with missing required fields."""
        provider_data = {
            "provider_name": "Test Hotel",
            # Missing provider_type, owner_id, created_by
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers",
            headers=superuser_token_headers,
            json=provider_data,
        )
        assert r.status_code == 422  # Validation error

    def test_create_stay_provider_invalid_uuid(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay provider creation with invalid UUID."""
        provider_data = {
            "provider_type": "hotel",
            "provider_name": "Test Hotel",
            "owner_id": "invalid-uuid",
            "created_by": "invalid-uuid",
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers",
            headers=superuser_token_headers,
            json=provider_data,
        )
        assert r.status_code == 422  # Validation error


class TestCreateStayUnit:
    """Test POST /stays/providers/{provider_id}/units endpoint."""

    def test_create_stay_unit_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """Test successful stay unit creation."""
        # Create a user and provider first
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Test Hotel",
            "owner_id": str(user.id),
            "created_by": str(user.id),
        }
        provider = ServiceProvider(**provider_data)
        created_provider = crud.create_service_provider(session=db, provider=provider)
        crud.create_stay_provider_row(session=db, provider_id=created_provider.id)

        unit_data = {
            "name": "Deluxe Room",
            "description": "A beautiful deluxe room",
            "room_rate": 150,
            "max_occupancy": 2,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{created_provider.id}/stay/units",
            headers=superuser_token_headers,
            json=unit_data,
        )
        assert r.status_code == 200
        created_unit = r.json()
        assert created_unit["name"] == "Deluxe Room"
        assert created_unit["room_rate"] == 150
        assert created_unit["provider_id"] == str(created_provider.id)

    def test_create_stay_unit_provider_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay unit creation with non-existent provider."""
        unit_data = {
            "name": "Deluxe Room",
            "description": "A beautiful deluxe room",
            "room_rate": 150,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{uuid.uuid4()}/stay/units",
            headers=superuser_token_headers,
            json=unit_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Provider not found"

    def test_create_stay_unit_requires_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that stay unit creation requires superuser privileges."""
        unit_data = {
            "name": "Deluxe Room",
            "description": "A beautiful deluxe room",
            "room_rate": 150,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{uuid.uuid4()}/stay/units",
            headers=normal_user_token_headers,
            json=unit_data,
        )
        assert r.status_code == 403

    def test_create_stay_unit_no_auth(self, client: TestClient) -> None:
        """Test stay unit creation without authentication."""
        unit_data = {
            "name": "Deluxe Room",
            "description": "A beautiful deluxe room",
            "room_rate": 150,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{uuid.uuid4()}/stay/units",
            json=unit_data,
        )
        assert r.status_code == 401

    def test_create_stay_unit_missing_name(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay unit creation without required name field."""
        unit_data = {
            "description": "A beautiful deluxe room",
            "room_rate": 150,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{uuid.uuid4()}/stay/units",
            headers=superuser_token_headers,
            json=unit_data,
        )
        assert r.status_code == 422  # Validation error


# Agency-specific comprehensive tests moved to tests/api/routes/test_agencies.py


class TestListStayUnits:
    """Test GET /stays/units endpoint."""

    def test_list_units_superuser_success(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test successful stay units listing by superuser."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        payload = r.json()
        assert "data" in payload and "count" in payload
        assert isinstance(payload["data"], list)
        assert isinstance(payload["count"], int)

    def test_list_units_with_filters(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay units listing with filters."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?min_price=100&max_price=200&limit=10&offset=0",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        payload = r.json()
        assert "data" in payload and "count" in payload

    def test_list_units_requires_agency_or_superuser(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """Test that stay units listing requires agency staff or superuser privileges."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized to query stay units"

    def test_list_units_no_auth(self, client: TestClient) -> None:
        """Test stay units listing without authentication."""
        r = client.get(f"{settings.API_V1_STR}/stays/units")
        assert r.status_code == 401

    def test_list_units_invalid_pagination(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay units listing with invalid pagination parameters."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?limit=-1&offset=-1",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error

    def test_list_units_invalid_price_filters(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay units listing with invalid price filters."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?min_price=abc&max_price=def",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error

    def test_list_units_invalid_provider_id(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test stay units listing with invalid provider ID."""
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?provider_id=invalid-uuid",
            headers=superuser_token_headers,
        )
        assert r.status_code == 422  # Validation error
