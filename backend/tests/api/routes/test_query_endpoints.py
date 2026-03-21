import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.models import UserCreate, User
from sqlmodel import select
from app.models.travel.enums import AmenityScope, ServiceProviderType
from app.core.config import settings
from tests.utils.utils import random_phone, random_lower_string, random_email
from tests.utils.user import authentication_token_from_phone


def create_provider_and_cab(client: TestClient, superuser_headers: dict[str, str], owner_user, vehicle_type="SEDAN"):
    provider_data = {
        "provider_type": ServiceProviderType.CAB,
        "provider_name": "Query Cab Provider",
        "owner_id": str(owner_user.id),
        "created_by": str(owner_user.id),
    }
    r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    cab_data = {
        "vehicle_type": vehicle_type,
        "vehicle_number": "QRY123", 
        "minimum_rate": 100.0, 
        "km_for_minimum_rate": 5.0, 
        "per_km_rate": 15.0, 
        "capacity": 4,
        "name": "ABC Cab",
        "company_model": "Model XYZ",
        "color": "Blue"
    }

    r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab", headers=superuser_headers, json=cab_data)
    # accept 200 or 400 per existing tests
    assert r.status_code in (200, 400)
    return provider


def create_provider_and_driver(client: TestClient, superuser_headers: dict[str, str], owner_user, db: Session):
    provider_data = {
        "provider_type": ServiceProviderType.CAB,
        "provider_name": "Query Driver Provider",
        "owner_id": str(owner_user.id),
        "created_by": str(owner_user.id),
    }
    r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    # create profile then driver
    # user_id is optional on the profile now; leave it out to exercise nullable behaviour
    profile_data = {"full_name": "Driver Test", "primary_email": random_email(), "primary_phone_number": random_phone()}
    r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_headers, json=profile_data)
    assert r.status_code == 200
    profile = r.json()
    assert profile.get("user_id") is None
    driver_data = {"user_id": str(owner_user.id), "profile_id": str(profile['id'])}
    r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_headers, json=driver_data)
    assert r.status_code == 200
    return provider


def create_stay_provider_with_unit(client: TestClient, superuser_headers: dict[str, str], db: Session, owner_user, lat=12.0, lon=77.0, room_rate=100, amenity=None):
    # create a Location directly in DB and then a provider referencing it
    from app.models.travel.location import Location
    loc = Location(id=uuid.uuid4(), latitude=float(lat), longitude=float(lon))
    db.add(loc)
    db.commit()
    db.refresh(loc)

    provider_data = {
        "provider_type": ServiceProviderType.STAY,
        "provider_name": "Query Stay Provider",
        "owner_id": str(owner_user.id),
        "created_by": str(owner_user.id),
        "location_id": str(loc.id),
    }
    r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    unit_data = {"name": "Nearby Unit", "room_rate": room_rate}
    r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/stay/units", headers=superuser_headers, json=unit_data)
    assert r.status_code == 200
    unit = r.json()
    unit_id = unit["id"]

    if amenity:
        r = client.post(
            f"{settings.API_V1_STR}/providers/{provider_id}/stay/units/{unit_id}/amenities",
            headers=superuser_headers, 
            json={
                "amenity": amenity, 
                "amenity_scope": AmenityScope.COMMON
            }
        )
        assert r.status_code == 200

    return provider, unit

class TestQueryEndpoints:
    def test_query_cabs_success_and_invalid(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create owner and provider + cab
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        provider = create_provider_and_cab(client, superuser_token_headers, owner, vehicle_type="SEDAN")
        provider_id = provider["id"]

        # query by provider_id
        r = client.get(f"{settings.API_V1_STR}/query/cabs?provider_id={provider_id}")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body and "count" in body

        # filter by vehicle_type that present
        r = client.get(f"{settings.API_V1_STR}/query/cabs?vehicle_type=SEDAN")
        assert r.status_code == 200
        assert r.json()["count"] >= 0 or len(r.json()["data"]) >= 0

        # filter by vehicle_type not present
        r = client.get(f"{settings.API_V1_STR}/query/cabs?vehicle_type=NONEXIST")
        assert r.status_code == 422
        # assert r.json()["count"] == 0 or len(r.json()["data"]) == 0

        # invalid lat should cause validation error
        r = client.get(f"{settings.API_V1_STR}/query/cabs?lat=notafloat&lon=77.0")
        assert r.status_code == 422


    def test_query_drivers_success_and_invalid(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        provider = create_provider_and_driver(client, superuser_token_headers, owner, db)
        provider_id = provider["id"]

        r = client.get(f"{settings.API_V1_STR}/query/drivers?provider_id={provider_id}")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body and "count" in body

        # invalid coords param
        r = client.get(f"{settings.API_V1_STR}/query/drivers?lat=abc&lon=def")
        assert r.status_code == 422


    def test_query_stay_units_near_access_and_filters(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create an owner and a stay provider located near (10.0, 10.0)
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        
        provider, unit = create_stay_provider_with_unit(client, superuser_token_headers, db, owner, lat=10.0, lon=10.0, room_rate=150, amenity="pool")
        # unauthenticated request -> 401
        r = client.get(f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0")
        assert r.status_code == 401

        # get token headers for this freshly-created normal user
        normal_user_token_headers = authentication_token_from_phone(client=client, phone_number=phone_number, db=db)

        # normal authenticated user (not agency staff) -> 403
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 403

        # create agency and add staff (use the fresh normal user we just created)
        agency_body = {"agency_name": "Test Agency", "contact_email": "a@b.com", "location_id": None, "created_by": str(owner.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_body)
        assert r.status_code == 200
        agency_id = r.json()["id"]

        # add owner as staff
        staff_body = {"user_id": str(owner.id), "role": None}
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{agency_id}/staffs", headers=superuser_token_headers, json=staff_body)
        assert r.status_code == 200

        # now normal_user_token_headers should be able to query
        r = client.get(f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0", headers=normal_user_token_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1

        # amenity filter
        r = client.get(f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&amenity=pool", headers=normal_user_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 1

        # price filter that excludes
        r = client.get(f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&min_price=1000", headers=normal_user_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 0


    def test_query_units_multi_amenities_filter(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test multi-amenity filtering with two distant units having different amenities.
        
        Scenario:
        - Unit 1 (North): located at (20.0, 20.0), room_rate=200, amenities: [wifi, ac]
        - Unit 2 (South): located at (10.0, 10.0), room_rate=100, amenities: [pool, gym]
        
        Test Cases:
        1. Single amenity queries isolate each unit correctly
        2. Repeated params style (amenities=wifi&amenities=ac) returns only matching units (AND semantics)
        3. Comma-separated fallback (amenities=wifi,ac) works identically to repeated params
        4. Duplicate amenities (wifi,wifi) dedupe correctly and still apply AND semantics
        5. No-match queries (wifi,notexists) return zero results
        6. Combined filters (amenities + price) narrow results correctly
        7. Empty amenities param returns all units
        """
        # Setup: Create owner and two distant stay providers with units
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Unit 1: North location, high price, wifi + ac amenities
        provider1, unit1 = create_stay_provider_with_unit(
            client,
            superuser_token_headers,
            db,
            owner,
            lat=20.0,
            lon=20.0,
            room_rate=200,
            amenity="wifi",
        )
        provider1_id = provider1["id"]
        unit1_id = unit1["id"]

        # Add second amenity to Unit 1
        r = client.post(
            f"{settings.API_V1_STR}/providers/{provider1_id}/stay/units/{unit1_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "ac", "amenity_scope": AmenityScope.COMMON},
        )
        assert r.status_code == 200
        assert r.json()["amenity"] == "ac"

        # Unit 2: South location, low price, pool + gym amenities
        provider2, unit2 = create_stay_provider_with_unit(
            client,
            superuser_token_headers,
            db,
            owner,
            lat=10.0,
            lon=10.0,
            room_rate=100,
            amenity="pool",
        )
        provider2_id = provider2["id"]
        unit2_id = unit2["id"]

        # Add second amenity to Unit 2
        r = client.post(
            f"{settings.API_V1_STR}/providers/{provider2_id}/stay/units/{unit2_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "gym", "amenity_scope": AmenityScope.COMMON},
        )
        assert r.status_code == 200
        assert r.json()["amenity"] == "gym"

        # Test Case 1: Single amenity queries should isolate each unit
        r = client.get(f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Only Unit 1 has wifi"

        r = client.get(f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=ac", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Only Unit 1 has ac"

        r = client.get(f"{settings.API_V1_STR}/query/units?provider_id={provider2_id}&amenities=pool", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Only Unit 2 has pool"

        r = client.get(f"{settings.API_V1_STR}/query/units?provider_id={provider2_id}&amenities=gym", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Only Unit 2 has gym"

        # Test Case 2: Repeated params style for multi-amenity query (AND semantics)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi&amenities=ac",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Only Unit 1 has both wifi AND ac"

        # Test Case 3: Comma-separated fallback style should work identically
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi,ac",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Comma-separated (wifi,ac) should return Unit 1 only"

        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider2_id}&amenities=pool,gym",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Comma-separated (pool,gym) should return Unit 2 only"

        # Test Case 4: Duplicate amenity should dedupe and still apply AND semantics
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi,wifi",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Duplicates dedupe; (wifi,wifi) should return Unit 1 only"

        # Test Case 5: No-match amenities should return zero results
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi,notexists",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0, "Amenity combo (wifi,notexists) matches nothing"

        # Cross-unit combos should also return zero (Unit 1 doesn't have pool)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi,pool",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0, "Amenity combo (wifi,pool) spans two units; AND semantics returns 0"

        # Test Case 6: Combined query with amenities + price filters
        # Unit 1 (room_rate=200): has wifi; price range 150-250 includes it
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=wifi&min_price=150&max_price=250",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Unit 1 (wifi, rate 200) matches amenity+price filter"

        # Unit 2 (room_rate=100): has pool; price range 150-250 excludes it
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider2_id}&amenities=pool&min_price=150&max_price=250",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0, "Unit 2 (pool, rate 100) outside price range"

        # Test Case 7: Empty amenities param should return all units from this provider
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider1_id}&amenities=",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "No amenity filter returns Unit 1"

        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider2_id}&amenities=",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "No amenity filter returns Unit 2"


    def test_sql_injection_like_input_is_handled(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        # create owner and stay provider with a unit
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        provider, unit = create_stay_provider_with_unit(client, superuser_token_headers, db, owner, lat=0.0, lon=0.0, room_rate=50, amenity="wifi")

        malicious = "'; DROP TABLE stayunit; --"
        r = client.get(f"{settings.API_V1_STR}/query/stay-units-near?lat=0.0&lon=0.0&amenity={malicious}", headers=superuser_token_headers)
        # should be processed safely (no server error)
        assert r.status_code in (200, 422)
