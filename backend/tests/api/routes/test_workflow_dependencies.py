"""
Workflow tests that test the dependencies between different API endpoints.
These tests ensure that the proper order of operations is maintained.
"""
import random
import uuid
from typing import Dict, Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from app.models.travel.providers import ServiceProvider
from app.models.travel.enums import ServiceProviderType, StaffRole
from app.models.travel.stay import StayUnit
from tests.utils.utils import random_email, random_lower_string


class TestUserToAgencyToStaffWorkflow:
    """
    Test the complete workflow: User Creation -> Agency Creation -> Staff Assignment -> Unit Listing
    This tests the dependency chain where each step requires the previous one to be completed.
    """

    def test_complete_workflow_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """
        Test the complete workflow from user creation to unit listing.
        This demonstrates the proper order of operations.
        """
        # Step 1: Create users (prerequisite for agency creation)
        username1 = random_email()
        password1 = random_lower_string()
        user_in1 = UserCreate(email=username1, password=password1)
        user1 = crud.create_user(session=db, user_create=user_in1)

        username2 = random_email()
        password2 = random_lower_string()
        user_in2 = UserCreate(email=username2, password=password2)
        user2 = crud.create_user(session=db, user_create=user_in2)

        # Step 2: Create travel agency (requires user1 to exist)
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(user1.id),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 200
        agency = r.json()
        agency_id = agency["id"]

        # Step 3: Assign staff to agency (requires both user2 and agency to exist)
        staff_data = {
            "user_id": str(user2.id),
            "role": "SUPPORT",
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency_id}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 200
        staff = r.json()

        # Step 4: Verify that user2 is now agency staff and can list units
        # First, get authentication token for user2
        login_data = {"username": username2, "password": password2}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 200
        tokens = r.json()
        user2_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Now user2 should be able to list stay units (as agency staff)
        r = client.get(
            f"{settings.API_V1_STR}/stays/units",
            headers=user2_headers,
        )
        assert r.status_code == 200
        units_response = r.json()
        assert "data" in units_response and "count" in units_response

    def test_workflow_fails_without_user_creation(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """
        Test that agency creation fails if the user doesn't exist.
        This demonstrates the dependency requirement.
        """
        # Try to create agency with non-existent user
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "contact@acme.com",
            "created_by": str(uuid.uuid4()),  # Non-existent user
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "User not found for created_by"

    def test_workflow_fails_without_agency_creation(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """
        Test that staff assignment fails if the agency doesn't exist.
        This demonstrates the dependency requirement.
        """
        # Create a user
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        # Try to assign staff to non-existent agency
        staff_data = {
            "user_id": str(user.id),
            "role": "AGENT",
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Agency not found"

    def test_workflow_fails_without_staff_assignment(
        self, client: TestClient, db: Session
    ) -> None:
        """
        Test that a normal user cannot list units without being agency staff.
        This demonstrates the permission requirement.
        """
        # Create a user but don't assign them as agency staff
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        crud.create_user(session=db, user_create=user_in)

        # Get authentication token for the user
        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 200
        tokens = r.json()
        user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # User should not be able to list stay units (not agency staff)
        r = client.get(f"{settings.API_V1_STR}/stays/units", headers=user_headers)
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized to query stay units"


class TestProviderToUnitWorkflow:
    """
    Test the workflow: Provider Creation -> Unit Creation
    This tests the dependency where units require providers to exist.
    """

    def test_provider_to_unit_workflow_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """
        Test the complete workflow from provider creation to unit creation.
        """
        # Step 1: Create a user (prerequisite for provider creation)
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        # Step 2: Create stay provider
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
        provider = r.json()
        provider_id = provider["id"]

        # Step 3: Create stay unit for the provider
        unit_data = {
            "name": "Deluxe Room",
            "description": "A beautiful deluxe room",
            "room_rate": 150,
            "max_occupancy": 2,
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/{provider_id}/stay/units",
            headers=superuser_token_headers,
            json=unit_data,
        )
        assert r.status_code == 200
        unit = r.json()
        assert unit["name"] == "Deluxe Room"
        assert unit["provider_id"] == provider_id
    


    def test_unit_creation_fails_without_provider(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """
        Test that unit creation fails if the provider doesn't exist.
        """
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


class TestComplexWorkflowWithMultipleEntities:
    """
    Test a complex workflow involving multiple users, agencies, providers, and units.
    This tests the system's ability to handle complex dependency chains.
    """

    def test_complex_workflow_success(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """
        Test a complex workflow with multiple entities and relationships.
        """
        # Create multiple users
        users = []
        for i in range(3):
            username = random_email()
            password = random_lower_string()
            user_in = UserCreate(email=username, password=password)
            user = crud.create_user(session=db, user_create=user_in)
            users.append({"user": user, "username": username, "password": password})

        # Create multiple agencies
        agencies = []
        for i, user_data in enumerate(users):
            agency_data = {
                "agency_name": f"Agency {i+1}",
                "contact_email": f"contact{i+1}@agency.com",
                "created_by": str(user_data["user"].id),
            }

            r = client.post(
                f"{settings.API_V1_STR}/travel-agency",
                headers=superuser_token_headers,
                json=agency_data,
            )
            assert r.status_code == 200
            agency = r.json()
            agencies.append(agency)

        # Create multiple providers
        providers = []
        for i, user_data in enumerate(users):
            provider_data = {
                "provider_type": ServiceProviderType.STAY,
                "provider_name": f"Hotel {i+1}",
                "owner_id": str(user_data["user"].id),
                "created_by": str(user_data["user"].id),
            }

            r = client.post(
                f"{settings.API_V1_STR}/providers",
                headers=superuser_token_headers,
                json=provider_data,
            )
            assert r.status_code == 201
            provider = r.json()
            providers.append(provider)

        # Assign staff to agencies
        for i, (agency, user_data) in enumerate(zip(agencies, users[1:], strict=False)):
            staff_data = {
                "user_id": str(user_data["user"].id),
                "role": random.choice(StaffRole._member_names_),
            }

            r = client.post(
                f"{settings.API_V1_STR}/travel-agency/{agency['id']}/staffs",
                headers=superuser_token_headers,
                json=staff_data,
            )
            assert r.status_code == 200

        # Create units for providers
        for i, provider in enumerate(providers):
            unit_data = {
                "name": f"Room {i+1}",
                "description": f"Description for room {i+1}",
                "room_rate": 100 + (i * 50),
                "max_occupancy": 2 + i,
            }

            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider['id']}/stay/units",
                headers=superuser_token_headers,
                json=unit_data,
            )
            assert r.status_code == 200

        # Verify that agency staff can list units
        for user_data in users[1:]:  # Skip the first user (not agency staff)
            login_data = {
                "username": user_data["username"],
                "password": user_data["password"],
            }
            r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
            assert r.status_code == 200
            tokens = r.json()
            user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

            r = client.get(
                f"{settings.API_V1_STR}/stays/units",
                headers=user_headers,
            )
            assert r.status_code == 200
            units_response = r.json()
            assert "data" in units_response and "count" in units_response

    def test_workflow_with_filtering_and_pagination(
        self, client: TestClient, superuser_token_headers: dict[str, str], db: Session
    ) -> None:
        """
        Test workflow with filtering and pagination capabilities.
        """
        # Create user, agency, staff, provider, and units
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        # Create agency
        agency_data = {
            "agency_name": "Test Agency",
            "contact_email": "test@agency.com",
            "created_by": str(user.id),
        }
        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 200
        agency = r.json()

        # Assign staff
        staff_data = {"user_id": str(user.id), "role": StaffRole.MANAGER}
        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency['id']}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 200

        # Create provider
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
        provider = r.json()

        # Create multiple units with different prices
        for i in range(5):
            unit_data = {
                "name": f"Room {i+1}",
                "description": f"Description {i+1}",
                "room_rate": 100 + (i * 25),  # 100, 125, 150, 175, 200
                "max_occupancy": 2,
            }

            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider['id']}/stay/units",
                headers=superuser_token_headers,
                json=unit_data,
            )
            assert r.status_code == 200

        # Get authentication token for the user
        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 200
        tokens = r.json()
        user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Test filtering by price range
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?min_price=120&max_price=180",
            headers=user_headers,
        )
        assert r.status_code == 200
        filtered_units = r.json()
        assert "data" in filtered_units

        # Test pagination
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?limit=2&offset=0",
            headers=user_headers,
        )
        assert r.status_code == 200
        paginated_units = r.json()
        assert "data" in paginated_units
        assert len(paginated_units["data"]) <= 2

        # Test filtering by provider
        r = client.get(
            f"{settings.API_V1_STR}/stays/units?provider_id={provider['id']}",
            headers=user_headers,
        )
        assert r.status_code == 200
        provider_units = r.json()
        assert "data" in provider_units


class TestWorkflowErrorHandling:
    """
    Test error handling in workflow scenarios.
    """

    def test_workflow_with_invalid_data_types(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """
        Test workflow with invalid data types to ensure proper error handling.
        """
        # Test with invalid UUID format
        agency_data = {
            "agency_name": "Test Agency",
            "contact_email": "test@agency.com",
            "created_by": "invalid-uuid-format",
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 422  # Validation error

    def test_workflow_with_missing_required_fields(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """
        Test workflow with missing required fields.
        """
        # Test agency creation without required fields
        agency_data = {
            "contact_email": "test@agency.com",
            # Missing agency_name and created_by
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 422  # Validation error

    def test_workflow_with_unauthorized_access(
        self, client: TestClient, db: Session
    ) -> None:
        """
        Test workflow with unauthorized access attempts.
        """
        # Create a normal user
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        crud.create_user(session=db, user_create=user_in)

        # Get authentication token for the user
        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        assert r.status_code == 200
        tokens = r.json()
        user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to create agency (should fail - requires superuser)
        agency_data = {
            "agency_name": "Test Agency",
            "contact_email": "test@agency.com",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=user_headers,
            json=agency_data,
        )
        assert r.status_code == 403

        # Try to create provider (should fail - requires superuser)
        provider_data = {
            "provider_type": "STAY",
            "provider_name": "Test Hotel",
            "owner_id": str(uuid.uuid4()),
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/providers/",
            headers=user_headers,
            json=provider_data,
        )
        assert r.status_code == 403
