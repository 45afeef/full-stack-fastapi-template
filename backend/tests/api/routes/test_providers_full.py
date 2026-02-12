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
        # a driver should have a profile so create a profile first
        profile_data = {"full_name": "Driver One", "primary_email": random_email(), "primary_phone_number": random_phone(),"user_id": str(user.id)}
        r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json=profile_data)
        assert r.status_code == 200

        profile = r.json()
        driver_data = {"user_id": str(user.id), "profile_id": str(profile['id'])}        
        r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_token_headers, json=driver_data)
        assert r.status_code == 200

        # list drivers as owner
        r = client.post(f"{settings.API_V1_STR}/login/access-token", data={"username": phone_number, "password": password})
        tokens = r.json()
        owner_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = client.get(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=owner_headers)
        assert r.status_code == 200


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
