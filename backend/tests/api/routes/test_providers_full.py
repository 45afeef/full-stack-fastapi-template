import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from app.models.travel.enums import ServiceProviderType
from tests.utils.utils import random_email, random_lower_string

class TestProviderCRUDAndPermissions:
    def test_provider_crud_and_permissions(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str] , db: Session):
        # Create a user who will be owner
        username = random_email()
        password = random_lower_string()
        user_in = UserCreate(email=username, password=password)
        owner = crud.create_user(session=db, user_create=user_in)

        # Superuser creates a provider
        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Test Provider",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 200
        provider = r.json()
        provider_id = provider["id"]

        # Unauthenticated request cannot create provider
        r = client.post(f"{settings.API_V1_STR}/providers/", json=provider_data)
        assert r.status_code == 401

        # Non-superuser cannot create provider
        r = client.post(f"{settings.API_V1_STR}/providers/", json=provider_data, headers=normal_user_token_headers)
        assert r.status_code == 403

        # Owner can get provider
        login_data = {"username": username, "password": password}
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
        tokens = r.json()
        owner_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.get(f"{settings.API_V1_STR}/providers/{provider_id}", headers=owner_headers)
        assert r.status_code == 200

        # Update provider as owner
        update_data = {"provider_name": "Updated Name"}
        r = client.patch(f"{settings.API_V1_STR}/providers/{provider_id}", headers=owner_headers, json={**provider_data, **update_data})
        assert r.status_code == 200

        # Delete provider as superuser
        r = client.delete(f"{settings.API_V1_STR}/providers/{provider_id}", headers=superuser_token_headers)
        assert r.status_code == 200

    def test_stay_unit_endpoints(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create owner and provider
        username = random_email()
        password = random_lower_string()
        user = crud.create_user(session=db, user_create=UserCreate(email=username, password=password))

        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Stay Provider",
            "owner_id": str(user.id),
            "created_by": str(user.id),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 200
        provider = r.json()
        provider_id = provider["id"]

        # create stay-specific row
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/stay/", headers=superuser_token_headers)
        assert r.status_code == 200

        # create a unit
        unit_data = {"name": "Unit A", "room_rate": 120}
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/stay/units", headers=superuser_token_headers, json=unit_data)
        assert r.status_code == 200

        # normal user cannot list units unless agency staff
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": username, "password": password})
        tokens = r.json()
        user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.get(f"{settings.API_V1_STR}/stays/units", headers=user_headers)
        assert r.status_code == 403
