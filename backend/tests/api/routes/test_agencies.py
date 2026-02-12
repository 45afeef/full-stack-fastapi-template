"""
Tests for agency endpoints (creation and staff assignment).
"""
import uuid

from fastapi.testclient import TestClient

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from app.models.travel.enums import StaffRole
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

    # Added test for missing mandatory fields
    # The API should return a 422 error if required fields are missing in the request payload
    # This test ensures that the API properly validates incoming data and enforces required fields for agency creation
    def test_create_agency_missing_required_fields(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """Test travel agency creation with missing required fields."""
        # 'agency_name' is a required field, so we omit it to test validation
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
        assert "agency_name" in r.json()["detail"][0]["loc"]  # Ensure the error is about the missing agency_name field
        
        # 'contact_email' is a required field, so we omit it to test validation
        agency_data = {
            "agency_name": "ACME Travel Agency",
            "created_by": str(uuid.uuid4()),
        }

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 422  # Validation error 
        assert "contact_email" in r.json()["detail"][0]["loc"]  # Ensure the error is about the missing contact_email field



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

        staff_data = {"user_id": str(user2.id), "role": StaffRole.OWNER}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency.id}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        
        assert r.status_code == 200
        created_staff = r.json()
        assert created_staff["user_id"] == str(user2.id)
        assert created_staff["role"] == "OWNER"
        assert "id" in created_staff

    def test_assign_agency_staff_agency_not_found(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session) -> None:
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        staff_data = {"user_id": str(user.id), "role": "AGENT"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Agency not found"

    def test_assign_agency_staff_requires_superuser(self, client: TestClient, normal_user_token_headers: dict[str, str], db:Session) -> None:
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        agency_data = {
            "agency_name": "ACME Travel Agency",
            "contact_email": "acme@example.com",
            "created_by": user.id,
        }
        agency_data = crud.create_travel_agency(session=db, agency=agency_data)
        staff_data = {"user_id": str(user.id), "role": StaffRole.AGENT}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency_data.id}/staffs",
            headers=normal_user_token_headers,
            json=staff_data,
        )

        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized to assign staff"        


    def test_assign_agency_staff_no_auth(self, client: TestClient) -> None:
        staff_data = {"user_id": str(uuid.uuid4()), "role": "SUPPORT"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            json=staff_data,
        )
        assert r.status_code == 401

    def test_assign_agency_staff_missing_user_id(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        staff_data = {"role": "OWNER"}

        r = client.post(
            f"{settings.API_V1_STR}/travel-agency/{uuid.uuid4()}/staffs",
            headers=superuser_token_headers,
            json=staff_data,
        )
        assert r.status_code == 422

class TestGetAgencies:
    def test_staff_no_memberships(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """Staff user with no memberships should get empty list."""
        email = random_email()
        pwd = random_lower_string()
        user_in = UserCreate(email=email, password=pwd)
        crud.create_user(session=db, user_create=user_in)

        from tests.utils.user import authentication_token_from_email
        token_headers = authentication_token_from_email(
            client=client, email=email, db=db
        )

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=token_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_staff_single_membership(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Staff user should see exactly one agency."""
        # Create agency owner
        owner_email = random_email()
        owner_pwd = random_lower_string()
        owner_in = UserCreate(email=owner_email, password=owner_pwd)
        owner = crud.create_user(session=db, user_create=owner_in)

        # Create staff user
        staff_email = random_email()
        staff_pwd = random_lower_string()
        staff_in = UserCreate(email=staff_email, password=staff_pwd)
        staff = crud.create_user(session=db, user_create=staff_in)

        # Create agency
        agency = crud.create_travel_agency(
            session=db,
            agency={
                "agency_name": "Test Agency 1",
                "contact_email": "agency1@test.com",
                "created_by": str(owner.id),
            },
        )

        # Assign staff
        client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency.id}/staffs",
            headers=superuser_token_headers,
            json={"user_id": str(staff.id), "role": StaffRole.AGENT},
        )

        from tests.utils.user import authentication_token_from_email
        staff_headers = authentication_token_from_email(
            client=client, email=staff_email, db=db
        )

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=staff_headers,
        )

        assert r.status_code == 200
        agencies = r.json()
        assert len(agencies) == 1
        assert agencies[0]["id"] == str(agency.id)
        assert agencies[0]["agency_name"] == "Test Agency 1"

    def test_staff_multiple_memberships(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Staff user should see all agencies they belong to."""
        owner = crud.create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(),
                password=random_lower_string(),
            ),
        )

        staff_email = random_email()
        staff_pwd = random_lower_string()
        staff = crud.create_user(
            session=db,
            user_create=UserCreate(email=staff_email, password=staff_pwd),
        )

        agencies = []
        for i in range(3):
            agency = crud.create_travel_agency(
                session=db,
                agency={
                    "agency_name": f"Agency {i}",
                    "contact_email": f"a{i}@test.com",
                    "created_by": str(owner.id),
                },
            )
            agencies.append(agency)

            client.post(
                f"{settings.API_V1_STR}/travel-agency/{agency.id}/staffs",
                headers=superuser_token_headers,
                json={"user_id": str(staff.id), "role": StaffRole.AGENT},
            )

        from tests.utils.user import authentication_token_from_email
        staff_headers = authentication_token_from_email(
            client=client, email=staff_email, db=db
        )

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=staff_headers,
        )

        assert r.status_code == 200
        result_ids = {a["id"] for a in r.json()}
        expected_ids = {str(a.id) for a in agencies}
        assert result_ids == expected_ids

    def test_superuser_sees_all_agencies(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        """Superuser should see all agencies regardless of staff."""
        owner = crud.create_user(
            session=db,
            user_create=UserCreate(
                email=random_email(),
                password=random_lower_string(),
            ),
        )

        agencies = [
            crud.create_travel_agency(
                session=db,
                agency={
                    "agency_name": f"Agency {i}",
                    "contact_email": f"a{i}@test.com",
                    "created_by": str(owner.id),
                },
            )
            for i in range(2)
        ]

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
        )

        assert r.status_code == 200
        returned_ids = {a["id"] for a in r.json()}
        for agency in agencies:
            assert str(agency.id) in returned_ids

    def test_get_agencies_unauthenticated(
        self,
        client: TestClient,
    ) -> None:
        """Unauthenticated request should return 401."""
        r = client.get(f"{settings.API_V1_STR}/travel-agency")
        assert r.status_code == 401

    def test_owner_not_staff_not_returned(
        self,
        client: TestClient,
        db: Session,
    ) -> None:
        """Creating an agency does not imply staff membership."""
        email = random_email()
        pwd = random_lower_string()
        user = crud.create_user(
            session=db,
            user_create=UserCreate(email=email, password=pwd),
        )

        crud.create_travel_agency(
            session=db,
            agency={
                "agency_name": "Owned Agency",
                "contact_email": "owned@test.com",
                "created_by": str(user.id),
            },
        )

        from tests.utils.user import authentication_token_from_email
        headers = authentication_token_from_email(
            client=client, email=email, db=db
        )

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=headers,
        )

        assert r.status_code == 200
        assert r.json() == []

    def test_staff_sees_agency_in_list(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        # create staff user
        staff_email = random_email()
        staff_pwd = random_lower_string()
        staff = crud.create_user(
            session=db,
            user_create=UserCreate(email=staff_email, password=staff_pwd),
        )

        # create agency
        agency = crud.create_travel_agency(
            session=db,
            agency={
                "agency_name": "Staff Agency",
                "contact_email": "staff@test.com",
                "created_by": str(staff.id),
            },
        )

        # assign staff
        client.post(
            f"{settings.API_V1_STR}/travel-agency/{agency.id}/staffs",
            headers=superuser_token_headers,
            json={"user_id": str(staff.id), "role": StaffRole.AGENT},
        )

        from tests.utils.user import authentication_token_from_email
        staff_headers = authentication_token_from_email(
            client=client, email=staff_email, db=db
        )

        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=staff_headers,
        )

        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["id"] == str(agency.id)

