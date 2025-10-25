import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from app.models.travel.enums import ServiceProviderType
from tests.utils.utils import random_email, random_lower_string


def test_create_and_delete_provider_workflow(client: TestClient, superuser_token_headers: dict[str, str], db: Session):
    # create a user
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    provider_data = {
        "provider_type": ServiceProviderType.STAY,
        "provider_name": "Test Provider",
        "owner_id": str(user.id),
        "created_by": str(user.id),
    }

    r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    # delete provider
    r = client.delete(f"{settings.API_V1_STR}/providers/{provider_id}", headers=superuser_token_headers)
    assert r.status_code == 200


def test_stay_unit_permissions(client: TestClient, superuser_token_headers: dict[str, str], db: Session):
    # create user and provider
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = crud.create_user(session=db, user_create=user_in)

    provider_data = {
        "provider_type": ServiceProviderType.STAY,
        "provider_name": "Unit Provider",
        "owner_id": str(user.id),
        "created_by": str(user.id),
    }
    r = client.post(f"{settings.API_V1_STR}/providers", headers=superuser_token_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    # create unit as superuser
    unit_data = {"name": "Room 1", "room_rate": 100}
    r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/stay/units", headers=superuser_token_headers, json=unit_data)
    assert r.status_code == 200

    # normal user should not list units unless agency staff
    login_data = {"username": username, "password": password}
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = client.get(f"{settings.API_V1_STR}/stays/units", headers=user_headers)
    assert r.status_code == 403
