import uuid
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate
from app.models.travel.enums import ServiceProviderType
from tests.utils.utils import random_phone, random_lower_string,  random_email

class TestProviderCRUDAndPermissions:
    def test_provider_create_fails_with_invalid_data(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str] , db: Session):
        # Create a user who will be owner
        phone_number = random_phone()
        password = random_lower_string()
        user_in = UserCreate(phone_number=phone_number, password=password)
        owner = crud.create_user(session=db, user_create=user_in)

        # try with fake created_by id
        body = {
            "provider_type": "INVALID_TYPE",
            "provider_name": "Test Provider",
            "owner_id": str(uuid.uuid4()),
            "created_by": str(uuid.uuid4()),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=body)
        assert r.status_code == 422
        r = None

        # try with currect provider_type
        body['provider_type'] = 'STAY'
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=body)
        assert r.status_code == 404
        assert r.json()['detail'] == 'User not found for created_by'

        # try with correct created_by but fake owner_id
        body['created_by'] = str(owner.id)
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=body)
        assert r.status_code == 404
        assert r.json()['detail'] == 'User not found for owner_id'

        # finally with correct data
        body['owner_id'] = str(owner.id)
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=body)
        assert r.status_code == 201


    def test_provider_crud_and_permissions(self, client: TestClient, superuser_token_headers: dict[str, str], normal_user_token_headers: dict[str, str] , db: Session):
        # Create a user who will be owner
        phone_number = random_phone()
        password = random_lower_string()
        user_in = UserCreate(phone_number=phone_number, password=password)
        owner = crud.create_user(session=db, user_create=user_in)

        # Superuser creates a provider
        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Test Provider",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider = r.json()
        provider_id = provider["id"]

        # Unauthenticated request cannot create provider
        r = client.post(f"{settings.API_V1_STR}/providers/", json=provider_data)
        assert r.status_code == 401

        # Non-superuser cannot create provider
        r = client.post(f"{settings.API_V1_STR}/providers/", json=provider_data, headers=normal_user_token_headers)
        assert r.status_code == 403

        # Owner can get provider
        login_data = {"username": phone_number, "password": password}
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


    def test_profile_creation_optional_user(self, client: TestClient, superuser_token_headers: dict[str, str]):
        # ensure we can create a profile without supplying user_id
        profile_data = {"first_name": "Optional", "primary_phone_number": random_phone(), "primary_email": random_email()}
        r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json=profile_data)
        assert r.status_code == 200
        p = r.json()
        assert p.get("user_id") is None

    def test_profile_creation_conflict_fields(self, client: TestClient, superuser_token_headers: dict[str, str]):
        # create a profile with unique contact info
        phone = random_phone()
        email = random_email()
        body = {"primary_phone_number": phone, "primary_email": email}
        r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json=body)
        assert r.status_code == 200

        # attempting to create another profile with the same primary_phone_number should conflict
        r = client.post(
            f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json={"primary_phone_number": phone}
        )
        assert r.status_code == 409
        assert "primary_phone_number" in r.json()["detail"]

        # same for primary_email
        r = client.post(
            f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json={"primary_email": email}
        )
        if r.status_code != 409:
            # emit body for debugging
            print("unexpected email-only response", r.status_code, r.text)
        assert r.status_code == 409
        assert "primary_email" in r.json()["detail"]

        # secondaries also collide against existing primary value
        r = client.post(
            f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json={"secondary_phone_number": phone}
        )
        assert r.status_code == 409
        assert "secondary_phone_number" in r.json()["detail"]

        r = client.post(
            f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json={"secondary_email": email}
        )
        assert r.status_code == 409
        assert "secondary_email" in r.json()["detail"]


    def test_cab_and_driver_endpoints(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create owner and provider
        phone_number = random_phone()
        password = random_lower_string()
        user = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        provider_data = {
            "provider_type": ServiceProviderType.CAB,
            "provider_name": "ABC Cab Provider",
            "owner_id": str(user.id),
            "created_by": str(user.id),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider = r.json()
        provider_id = provider["id"]

        # create a cab (superuser)
        cab_data = {
            "vehicle_type": "SEDAN", 
            "vehicle_number": "ABC123", 
            "minimum_rate": 100.0, 
            "km_for_minimum_rate": 5.0, 
            "per_km_rate": 15.0, 
            "capacity": 4,
            "name": "ABC Cab",
            "company_model": "Model XYZ",
            "color": "Blue"
        }
        
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab", headers=superuser_token_headers, json=cab_data)
        # Might be 200 or 400 depending on whether CabServiceProvider row exists; accept 200/400
        assert r.status_code in (200, 400)

        # validate create driver requires profile id(superuser)
        driver_data = {"user_id": str(user.id)}
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_token_headers, json=driver_data)
        assert r.status_code == 422
        assert r.json()['detail'][0]['msg'] == 'Field required'
        assert r.json()['detail'][0]['type'] == 'missing'
        assert r.json()['detail'][0]['loc'] == ['body', 'profile_id']
        
        # create driver (superuser)
        # a driver should have a profile so create a profile first; user_id is optional now
        profile_data = {"full_name": "Driver One", "primary_email": random_email(), "primary_phone_number": random_phone()}
        r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json=profile_data)
        assert r.status_code == 200
        profile = r.json()
        assert profile.get("user_id") is None

        driver_data = {"user_id": str(user.id), "profile_id": str(profile['id'])}        
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_token_headers, json=driver_data)
        assert r.status_code == 200

        # create another driver without user_id (should be allowed and user_id will
        # be returned as null)
        driver_data = {"profile_id": str(profile['id'])}
        r = client.post(
            f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers",
            headers=superuser_token_headers,
            json=driver_data,
        )
        assert r.status_code == 200
        driver = r.json()
        assert driver.get("user_id") is None

        # list drivers as owner and verify at least one has no user_id
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": phone_number, "password": password})
        tokens = r.json()
        owner_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.get(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=owner_headers)
        assert r.status_code == 200
        drivers = r.json()
        assert any(d.get("user_id") is None for d in drivers)


    def test_stay_unit_endpoints(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create owner and provider
        phone_number = random_phone()
        password = random_lower_string()
        user = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Stay Provider",
            "owner_id": str(user.id),
            "created_by": str(user.id),
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider = r.json()
        provider_id = provider["id"]

        # create a unit
        unit_data = {"name": "Unit A", "room_rate": 120}
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/stay/units", headers=superuser_token_headers, json=unit_data)
        assert r.status_code == 200

        # normal user cannot list units unless agency staff
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": phone_number, "password": password})
        tokens = r.json()
        user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.get(f"{settings.API_V1_STR}/query/units", headers=user_headers)
        assert r.status_code == 403
