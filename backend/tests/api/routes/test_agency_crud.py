"""
Tests for enhanced agency CRUD and staff management.
"""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from tests.utils.utils import random_email, random_lower_string


class TestAgencyCRUD:
    def test_full_agency_crud_as_superuser(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers:dict[str, str],db: Session) -> None:
        # create user
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        user = crud.create_user(session=db, user_create=user_in)

        # create agency as superuser
        agency_data = {"agency_name": "New Agency", "contact_email": "a@test.com", "created_by": str(user.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_data)
        assert r.status_code == 200
        agency = r.json()
        aid = agency["id"]

        # get detail
        r = client.get(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=superuser_token_headers)
        assert r.status_code == 200

        # update agency
        r = client.put(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=superuser_token_headers, json={"agency_name": "Updated"})
        assert r.status_code == 200

        # verify no other users can access crud ops
        r = client.get(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=normal_user_token_headers)
        assert r.status_code == 403
        r = client.put(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=normal_user_token_headers, json={"agency_name": "Hacked"})
        assert r.status_code == 403
        r = client.delete(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=normal_user_token_headers)
        assert r.status_code == 403
        r = client.get(f"{settings.API_V1_STR}/travel-agency", headers=normal_user_token_headers)
        assert r.status_code == 403
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=normal_user_token_headers, json=agency_data)
        assert r.status_code == 403
        
        # delete agency as superuser
        r = client.delete(f"{settings.API_V1_STR}/travel-agency/{aid}", headers=superuser_token_headers)
        assert r.status_code == 200

    def test_owner_can_manage_staff_but_not_delete_agency(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str], db: Session) -> None:
        # create owner user
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        owner = crud.create_user(session=db, user_create=user_in)

        # create another user
        username2 = random_email()
        password2 = random_lower_string()
        user2 = crud.create_user(session=db, user_create=UserCreate(email=username2, password=password2))

        # superuser creates agency with owner as created_by
        agency_data = {"agency_name": "Owner Agency", "created_by": str(owner.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_data)
        assert r.status_code == 200
        agency = r.json()
        aid = agency["id"]

        # owner logs in
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": username, "password": password})
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
        username = random_email()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(email=username, password=password))
        other = crud.create_user(session=db, user_create=UserCreate(email=random_email(), password=random_lower_string()))

        # superuser creates agency
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json={"agency_name": "A", "created_by": str(owner.id)})
        agency = r.json()
        aid = agency['id']

        # normal user tries to assign staff
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{aid}/staffs", headers=normal_user_token_headers, json={"user_id": str(other.id), "role": "AGENT"})
        assert r.status_code == 403
