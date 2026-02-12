"""
Tests for enhanced agency CRUD and staff management.
"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.utils import random_phone, random_lower_string

class TestAgencyCRUD:
    def test_full_agency_crud_as_superuser(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        normal_user_token_headers: dict[str, str],
        db: Session,
    ) -> None:
        # create user
        phone_number = random_phone()
        password = random_lower_string()
        user_in = UserCreate(phone_number=phone_number, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        # create agency as superuser
        agency_data = {
            "agency_name": "New Agency",
            "contact_email": "a@test.com",
            "created_by": str(user.id),
        }
        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=superuser_token_headers,
            json=agency_data,
        )
        assert r.status_code == 200
        agency = r.json()
        aid = agency["id"]

        # get detail as superuser
        r = client.get(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

        # update agency as superuser
        r = client.put(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=superuser_token_headers,
            json={"agency_name": "Updated"},
        )
        assert r.status_code == 200
        assert r.json()["agency_name"] == "Updated"

        # verify normal user cannot access detail/update/delete
        r = client.get(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized to view agency"

        r = client.put(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=normal_user_token_headers,
            json={"agency_name": "Hacked"},
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Not authorized to update agency"

        r = client.delete(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "The user doesn't have enough privileges"

        # normal user CAN list agencies (but sees none)
        r = client.get(
            f"{settings.API_V1_STR}/travel-agency",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

        # normal user cannot create agencies
        r = client.post(
            f"{settings.API_V1_STR}/travel-agency",
            headers=normal_user_token_headers,
            json=agency_data,
        )
        assert r.status_code == 403

        # delete agency as superuser
        r = client.delete(
            f"{settings.API_V1_STR}/travel-agency/{aid}",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200

    def test_owner_can_manage_staff_but_not_delete_agency(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str], db: Session) -> None:
        # create owner user
        phone_number = random_phone()
        password = random_lower_string()
        user_in = UserCreate(phone_number=phone_number, password=password)
        owner = crud.create_user(session=db, user_create=user_in)

        # create another user
        phone_number2 = random_phone()
        password2 = random_lower_string()
        user2 = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number2, password=password2))

        # superuser creates agency
        agency_data = {"agency_name": "Owner Agency", "contact_email":"agency@company.com"}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_data)
        assert r.status_code == 200
        agency = r.json()
        aid = agency["id"]

        # superuser assigns owner
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{aid}/staffs", headers=superuser_token_headers, json={"user_id": str(owner.id), "role": "OWNER"})
        assert r.status_code == 200

        # owner logs in
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": phone_number, "password": password})
        assert r.status_code == 200
        tokens = r.json()
        owner_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # owner assigns staff
        staff_data = {"user_id": str(user2.id), "role": "AGENT"}
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{aid}/staffs", headers=owner_headers, json=staff_data)
        assert r.status_code == 200
        staff = r.json()

        # owner updates staff
        r = client.patch(f"{settings.API_V1_STR}/travel-agency/{aid}/staffs/{staff['id']}", headers=owner_headers, json={"role": "MANAGER"})
        assert r.status_code == 200

        # owner cannot delete agency
        r = client.delete(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=owner_headers)
        assert r.status_code == 403

    def test_non_owner_cannot_manage_staff(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str], db: Session) -> None:
        # create owner and other user
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        other = crud.create_user(session=db, user_create=UserCreate(phone_number=random_phone(), password=random_lower_string()))

        # superuser creates agency
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json={"agency_name": "A", "contact_email":"agency@company.com"})
        agency = r.json()
        aid = agency['id']

        # normal user tries to assign staff
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{aid}/staffs", headers=normal_user_token_headers, json={"user_id": str(other.id), "role": "AGENT"})
        assert r.status_code == 403
    
    # Test that agency creation fails without contact_email or name
    def test_agency_creation_requires_fields(self, client: TestClient, superuser_token_headers: dict[str, str]) -> None:
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json={"agency_name": "No Contact"})
        assert r.status_code == 422

        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json={"contact_email": "no-agency-name@example.com"})
        assert r.status_code == 422