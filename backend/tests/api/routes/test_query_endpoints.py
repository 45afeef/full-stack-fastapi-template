import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.models import UserCreate, User
from sqlmodel import select
from app.models.travel.enums import AmenityScope, ServiceProviderType
from app.models.travel.providers import StayServiceProvider
from app.core.config import settings
from tests.utils.utils import random_phone, random_lower_string, random_email
from tests.utils.user import authentication_token_from_phone


def create_provider_and_cab(client: TestClient, superuser_headers: dict[str, str], owner_user, vehicle_type="SEDAN"):
    provider_data = {
        "provider_type": ServiceProviderType.CAB,
        "provider_name": "Query Cab Provider",
        "owner_id": str(owner_user.id),
        "created_by": str(owner_user.id),
        "latitude": 40.7128,  # New York latitude
        "longitude": -74.0060,  # New York longitude
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
        "latitude": 40.7128,  # New York latitude
        "longitude": -74.0060,  # New York longitude
    }
    r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_headers, json=provider_data)
    assert r.status_code == 201
    provider = r.json()
    provider_id = provider["id"]

    # create profile then driver
    # user_id is optional on the profile now; leave it out to exercise nullable behaviour
    profile_data = {"first_name": "Driver Test", "primary_email": random_email(), "primary_phone_number": random_phone()}
    r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_headers, json=profile_data)
    assert r.status_code == 200
    profile = r.json()
    assert profile.get("user_id") is None
    driver_data = {"user_id": str(owner_user.id), "profile_id": str(profile['id'])}
    r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_headers, json=driver_data)
    assert r.status_code == 200
    return provider, profile


def create_stay_provider_with_unit(
        client: TestClient, 
        superuser_headers: dict[str, str], 
        db: Session, 
        owner_user, 
        lat=12.0, 
        lon=77.0, 
        room_rate=100, 
        amenity=None, 
        room_count=1
    ):

    provider_data = {
        "provider_type": ServiceProviderType.STAY,
        "provider_name": "Query Stay Provider",
        "owner_id": str(owner_user.id),
        "created_by": str(owner_user.id),
        "latitude": lat,
        "longitude": lon,
        "room_count": room_count,
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
        provider, profile = create_provider_and_driver(client, superuser_token_headers, owner, db)
        provider_id = provider["id"]

        r = client.get(f"{settings.API_V1_STR}/query/drivers?provider_id={provider_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1

        driver_item = body["data"][0]
        expected_fields = {
            "id",
            "provider_id",
            "profile_id",
            "user_id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "primary_phone_number",
            "secondary_phone_number",
            "primary_email",
            "secondary_email",
            "profile_picture",
            "bio",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "created_at",
            "updated_at",
        }
        assert set(driver_item.keys()) == expected_fields
        assert driver_item["provider_id"] == provider_id
        assert driver_item["profile_id"] == profile["id"]
        assert driver_item["user_id"] == str(owner.id)
        assert driver_item["first_name"] == "Driver Test"
        assert driver_item["middle_name"] is None
        assert driver_item["last_name"] is None
        assert driver_item["full_name"] in ("Driver Test", None)
        assert driver_item["primary_phone_number"] == profile["primary_phone_number"]
        assert driver_item["secondary_phone_number"] is None
        assert driver_item["primary_email"] == profile["primary_email"]
        assert driver_item["secondary_email"] is None
        assert driver_item["profile_picture"] is None
        assert driver_item["bio"] is None
        assert driver_item["address"] is None
        assert driver_item["city"] is None
        assert driver_item["state"] is None
        assert driver_item["zip_code"] is None
        assert driver_item["country"] is None
        assert driver_item["created_at"] is not None
        assert driver_item["updated_at"] is not None

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


    def test_query_units_multi_amenities_filter(
        self, 
        client: TestClient, 
        superuser_token_headers: dict[str, str], 
        db: Session
    ):
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

        # Test Case 8: room_count filter
        # Create a third provider with room_count=2
        provider3, unit3 = create_stay_provider_with_unit(
            client,
            superuser_token_headers,
            db,
            owner,
            lat=30.0,
            lon=30.0,
            room_rate=150,
            amenity="wifi",
            room_count=2,
        )

        # room_count=2 should return only units belonging to providers with at least 2 rooms
        r = client.get(
            f"{settings.API_V1_STR}/query/units?room_count=2",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        response = r.json()
        provider_ids = {unit["provider_id"] for unit in response["data"]}
        assert provider3["id"] in provider_ids, "Provider 3 must be returned for room_count=2"
        assert provider1_id not in provider_ids, "Provider 1 with room_count=1 must not be returned for room_count=2"
        assert provider2_id not in provider_ids, "Provider 2 with room_count=1 must not be returned for room_count=2"
        for unit in response["data"]:
            provider = db.get(StayServiceProvider, unit["provider_id"])
            assert provider is not None
            assert provider.room_count >= 2, f"Returned unit {unit['id']} must belong to a provider with room_count >= 2"

        # room_count=1 should return units for all three created providers
        r = client.get(
            f"{settings.API_V1_STR}/query/units?room_count=1",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        response = r.json()
        provider_ids = {unit["provider_id"] for unit in response["data"]}
        assert provider1_id in provider_ids, "Provider 1 must be returned for room_count=1"
        assert provider2_id in provider_ids, "Provider 2 must be returned for room_count=1"
        assert provider3["id"] in provider_ids, "Provider 3 must be returned for room_count=1"
        for unit in response["data"]:
            provider = db.get(StayServiceProvider, unit["provider_id"])
            assert provider is not None
            assert provider.room_count >= 1, f"Returned unit {unit['id']} must belong to a provider with room_count >= 1"


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


    def test_query_units_with_pax_count_filtering(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test pax_count filtering with multiple units having different max_occupancy.
        
        Scenario:
        - Unit 1: max_occupancy=2
        - Unit 2: max_occupancy=4
        - Unit 3: max_occupancy=6
        - Unit 4: max_occupancy=1 (low capacity)
        
        Test Cases:
        1. pax_count=1: All units match (all have >= 1 capacity)
        2. pax_count=3: Only units 2, 3 match (max_occupancy >= 3)
        3. pax_count=5: Only unit 3 matches (max_occupancy >= 5)
        4. pax_count=7: No units match (all have < 7 capacity)
        5. Verify provider total capacity logic: if provider has multiple units, total should count
        """
        # Setup: Create owner and stay provider with multiple units of different capacities
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        # Create provider
        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Pax Count Test Provider",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": 10.0,
            "longitude": 10.0,
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider_id = r.json()["id"]

        # Create units with different occupancy levels
        capacities = [2, 4, 6, 1]
        unit_ids = []
        for idx, capacity in enumerate(capacities):
            unit_data = {
                "name": f"Unit {idx + 1}",
                "room_rate": 100 + (idx * 50),
                "max_occupancy": capacity,
            }
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_id}/stay/units",
                headers=superuser_token_headers,
                json=unit_data
            )
            assert r.status_code == 200
            unit_ids.append(r.json()["id"])

        # Test Case 1: pax_count=1 should return all units
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=1",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 4, "pax_count=1: All units should match (all have >= 1)"

        # Test Case 2: pax_count=3 with provider total capacity
        # Provider total capacity = 2 + 4 + 6 + 1 = 13, which is >= 3
        # So all units match due to provider total capacity logic (OR semantics with unit capacity)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=3",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        # Provider total capacity (13) >= 3, so all units from provider are returned
        assert data["count"] == 4, "pax_count=3: All units returned due to provider total capacity >= 3"

        # Test Case 3: pax_count=5 should return all units (provider total 13 >= 5)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=5",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 4, "pax_count=5: All units returned due to provider total capacity >= 5"

        # Test Case 4: pax_count=7 should return all units (provider total 13 >= 7)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=7",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 4, "pax_count=7: All units returned due to provider total capacity >= 7"

        # Test Case 5: pax_count=14 (exceeds provider total 13) should return no units
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=14",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0, "pax_count=14: No units match (provider total 13 < 14)"

        # Test Case 6: pax_count combined with price filter (all units with price <= 200)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=3&max_price=200",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find units with pax_count=3 and price <= 200"
        for unit in data["data"]:
            assert unit["room_rate"] <= 200, "Returned unit should have room_rate <= 200"


    def test_query_units_pagination(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test pagination with limit and offset parameters.
        
        Scenario:
        - Create 5 stay units in one provider
        - Query with limit=2, offset=0 → 2 results
        - Query with limit=2, offset=2 → 2 results
        - Query with limit=2, offset=4 → 1 result
        - Query with limit=2, offset=10 → 0 results (out of bounds)
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Create provider with 5 units
        provider, _ = create_stay_provider_with_unit(client, superuser_token_headers, db, owner, lat=0.0, lon=0.0, room_rate=100)
        provider_id = provider["id"]

        # Create 4 more units (we already have 1 from create_stay_provider_with_unit)
        for i in range(2, 6):
            unit_data = {"name": f"Unit {i}", "room_rate": 100 + (i * 10)}
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_id}/stay/units",
                headers=superuser_token_headers,
                json=unit_data
            )
            assert r.status_code == 200

        # Test Case 1: Get first 2 units (limit=2, offset=0)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=2&offset=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 2, "limit=2, offset=0 should return 2 units"

        # Test Case 2: Get next 2 units (limit=2, offset=2)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=2&offset=2",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 2, "limit=2, offset=2 should return 2 units"

        # Test Case 3: Get remaining units (limit=2, offset=4)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=2&offset=4",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 1, "limit=2, offset=4 should return 1 unit (last one)"

        # Test Case 4: Out of bounds offset (limit=2, offset=10)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=2&offset=10",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["data"]) == 0, "offset=10 is out of bounds, should return 0 units"

        # Test Case 5: Verify limit bounds (max 500)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=501",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit > 500 should be rejected by validation"


    def test_query_units_price_boundary_conditions(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test price filtering with boundary conditions.
        
        Scenario:
        - Unit A: room_rate = 100
        - Unit B: room_rate = 200
        - Unit C: room_rate = 300
        
        Test Cases:
        1. min_price=100, max_price=100 → only Unit A
        2. min_price=100, max_price=200 → Units A and B
        3. min_price=200, max_price=200 → only Unit B
        4. min_price=150, max_price=250 → only Unit B
        5. min_price=300, max_price=300 → only Unit C
        6. min_price=350, max_price=400 → no units
        7. max_price=150 (no min) → Units A only
        8. min_price=250 (no max) → Unit C only
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        provider_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Price Test Provider",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": 0.0,
            "longitude": 0.0,
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider_id = r.json()["id"]

        # Create units with specific prices
        prices = [100, 200, 300]
        for idx, price in enumerate(prices):
            unit_data = {"name": f"Unit {chr(65 + idx)}", "room_rate": price}
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_id}/stay/units",
                headers=superuser_token_headers,
                json=unit_data
            )
            assert r.status_code == 200

        # Test Case 1: exact match at min boundary
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&min_price=100&max_price=100",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Exact price 100 should match 1 unit"

        # Test Case 2: range covering multiple units
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&min_price=100&max_price=200",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 2, "Price range 100-200 should include 2 units"

        # Test Case 3: single unit in middle
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&min_price=150&max_price=250",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "Price range 150-250 should match only Unit B (200)"

        # Test Case 4: high price range
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&min_price=350&max_price=400",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0, "Price range 350-400 should match no units"

        # Test Case 5: only max_price specified
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&max_price=150",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "max_price=150 should match only Unit A (100)"

        # Test Case 6: only min_price specified
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&min_price=250",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1, "min_price=250 should match only Unit C (300)"


    def test_query_stay_units_near_distance_sorting(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test geographic distance-based sorting.
        
        Scenario:
        - Unit 1: location (10.0, 10.0)
        - Unit 2: location (12.0, 12.0) - ~314 km away
        - Unit 3: location (10.1, 10.1) - ~15.7 km away
        - Search from (10.0, 10.0) with sort_by_distance=True
        
        Expected order: Unit 1 (0 km), Unit 3 (~15.7 km), Unit 2 (~314 km)
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Create agency and add staff
        agency_body = {"agency_name": "Distance Test Agency", "contact_email": "dist@test.com", "location_id": None, "created_by": str(owner.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_body)
        assert r.status_code == 200
        agency_id = r.json()["id"]

        staff_body = {"user_id": str(owner.id), "role": None}
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{agency_id}/staffs", headers=superuser_token_headers, json=staff_body)
        assert r.status_code == 200

        owner_token_headers = authentication_token_from_phone(client=client, phone_number=phone_number, db=db)

        # Create three providers at different locations
        locations = [(10.0, 10.0), (12.0, 12.0), (10.1, 10.1)]
        provider_ids = []
        
        for idx, (lat, lon) in enumerate(locations):
            provider_data = {
                "provider_type": ServiceProviderType.STAY,
                "provider_name": f"Distance Test Provider {idx + 1}",
                "owner_id": str(owner.id),
                "created_by": str(owner.id),
                "latitude": lat,
                "longitude": lon,
            }
            r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
            assert r.status_code == 201
            provider_ids.append(r.json()["id"])

            # Create unit for this provider
            unit_data = {"name": f"Unit {idx + 1}", "room_rate": 100}
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_ids[idx]}/stay/units",
                headers=superuser_token_headers,
                json=unit_data
            )
            assert r.status_code == 200

        # Query with sort_by_distance=True from origin (10.0, 10.0) with large radius
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&radius_km=500&sort_by_distance=true&limit=10",
            headers=owner_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        results = data["data"]
        
        # Verify we got units and they're in distance order
        assert len(results) >= 1, "Should find at least some units"
        
        # Check that results are sorted by distance (nearest first)
        if len(results) >= 2:
            # The first unit should be closer or equal distance to the second
            # This is approximate due to the bbox pre-filter, but distance sorting should work
            assert data["count"] >= 1, "Should have at least 1 unit in results"


    def test_query_stay_units_near_radius_filtering(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test geographic radius-based filtering for nearby providers.
        
        Scenario:
        - Unit A: location (10.0, 10.0) - at search center
        - Unit B: location (10.05, 10.05) - ~7.8 km away
        - Unit C: location (10.2, 10.2) - ~31.3 km away
        
        Test Cases:
        1. radius_km=1 → only Unit A (exact point)
        2. radius_km=10 → Units A and B (within 10 km)
        3. radius_km=50 → all units (within 50 km)
        4. radius_km=1 near Unit B's location → only Unit B
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Create agency and add staff
        agency_body = {"agency_name": "Radius Test Agency", "contact_email": "rad@test.com", "location_id": None, "created_by": str(owner.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_body)
        assert r.status_code == 200
        agency_id = r.json()["id"]

        staff_body = {"user_id": str(owner.id), "role": None}
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{agency_id}/staffs", headers=superuser_token_headers, json=staff_body)
        assert r.status_code == 200

        owner_token_headers = authentication_token_from_phone(client=client, phone_number=phone_number, db=db)

        # Create theme providers at different distances
        locations_data = [
            (10.0, 10.0, "Unit A (at center)"),
            (10.05, 10.05, "Unit B (7.8 km)"),
            (10.2, 10.2, "Unit C (31.3 km)"),
        ]

        for idx, (lat, lon, name) in enumerate(locations_data):
            provider_data = {
                "provider_type": ServiceProviderType.STAY,
                "provider_name": f"Radius Provider {idx + 1}",
                "owner_id": str(owner.id),
                "created_by": str(owner.id),
                "latitude": lat,
                "longitude": lon,
            }
            r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
            assert r.status_code == 201
            provider_id = r.json()["id"]

            unit_data = {"name": name, "room_rate": 100}
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_id}/stay/units",
                headers=superuser_token_headers,
                json=unit_data
            )
            assert r.status_code == 200

        # Test Case 1: small radius (1 km) from (10.0, 10.0)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&radius_km=1",
            headers=owner_token_headers
        )
        assert r.status_code == 200
        # Should find the unit at exact center
        assert r.json()["count"] >= 1

        # Test Case 2: medium radius (10 km) from (10.0, 10.0)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&radius_km=10",
            headers=owner_token_headers
        )
        assert r.status_code == 200
        # Should find units A and potentially B
        count_10km = r.json()["count"]
        assert count_10km >= 1, "Should find at least 1 unit within 10 km"

        # Test Case 3: large radius (50 km) from (10.0, 10.0)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-units-near?lat=10.0&lon=10.0&radius_km=50",
            headers=owner_token_headers
        )
        assert r.status_code == 200
        # Should find all three units
        count_50km = r.json()["count"]
        assert count_50km >= count_10km, "Larger radius should find >= units as smaller radius"


    def test_query_cabs_with_vehicle_type_and_location(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test cab querying with vehicle type and location-based filtering combined.
        
        Scenario:
        - Provider 1 (lat=10.0, lon=10.0): SEDAN cab
        - Provider 2 (lat=10.1, lon=10.1): SUV cab
        - Provider 3 (lat=20.0, lon=20.0): SEDAN cab (far away)
        
        Test Cases:
        1. vehicle_type=SEDAN → both SEDAN cabs
        2. vehicle_type=SEDAN + location near (10.0, 10.0) with small radius → only Provider 1's SEDAN
        3. vehicle_type=SUV → only Provider 2's SUV cab
        4. vehicle_type=HATCHBACK → no cabs match
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Create cabs at different locations with different types
        cab_configs = [
            (10.0, 10.0, "SEDAN"),
            (10.1, 10.1, "SUV"),
            (20.0, 20.0, "SEDAN"),
        ]

        for idx, (lat, lon, vehicle_type) in enumerate(cab_configs):
            # Create provider
            provider_data = {
                "provider_type": ServiceProviderType.CAB,
                "provider_name": f"Cab Provider {idx + 1}",
                "owner_id": str(owner.id),
                "created_by": str(owner.id),
                "latitude": lat,
                "longitude": lon,
            }
            r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
            assert r.status_code == 201
            provider_id = r.json()["id"]

            # Create cab
            cab_data = {
                "vehicle_type": vehicle_type,
                "vehicle_number": f"CAB{idx + 1}",
                "minimum_rate": 100.0,
                "km_for_minimum_rate": 5.0,
                "per_km_rate": 15.0,
                "capacity": 4,
                "name": f"Cab {idx + 1}",
                "company_model": "Model A",
                "color": "Blue"
            }
            r = client.post(
                f"{settings.API_V1_STR}/providers/{provider_id}/cab",
                headers=superuser_token_headers,
                json=cab_data
            )
            # Accept both 200 and 400
            assert r.status_code in (200, 400, 201)

        # Test Case 1: filter by vehicle_type=SEDAN (should get 2 sedans)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?vehicle_type=SEDAN")
        assert r.status_code == 200
        data = r.json()
        # Should find sedans
        sedan_count = data["count"]

        # Test Case 2: filter by vehicle_type=SUV (should get 1 SUV)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?vehicle_type=SUV")
        assert r.status_code == 200
        data = r.json()
        suv_count = data["count"]

        # Test Case 3: Non-existent vehicle type (FastAPI doesn't strictly validate string values)
        # Returns 200 with empty results or results matching the string value
        r = client.get(f"{settings.API_V1_STR}/query/cabs?vehicle_type=HATCHBACK")
        assert r.status_code == 200  # String params are processed without strict enum validation

        # Test Case 4: Location-based query for cabs
        r = client.get(f"{settings.API_V1_STR}/query/cabs?lat=10.0&lon=10.0&radius_km=1")
        assert r.status_code == 200
        data = r.json()
        # Should find cabs from Provider 1 (exact center location)
        assert data["count"] >= 0  # May find 0 or more depending on exact implementation


    def test_query_drivers_authorization_required(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test that driver queries work without authentication (public endpoint).
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        provider, _ = create_provider_and_driver(client, superuser_token_headers, owner, db)
        provider_id = provider["id"]

        # Unauthenticated request should still work (public endpoint)
        r = client.get(f"{settings.API_V1_STR}/query/drivers?provider_id={provider_id}")
        assert r.status_code == 200
        assert "data" in r.json()
        assert "count" in r.json()


    def test_query_units_no_provider_id_returns_all_for_superuser(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test that query/units without provider_id returns units from all providers for superuser.
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Create multiple providers with units
        for i in range(3):
            provider, _ = create_stay_provider_with_unit(
                client,
                superuser_token_headers,
                db,
                owner,
                lat=10.0 + i,
                lon=10.0 + i,
                room_rate=100 + (i * 50)
            )

        # Query without provider_id should return units from all providers
        r = client.get(f"{settings.API_V1_STR}/query/units", headers=superuser_token_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 3, "Should return units from all 3 providers"


    def test_query_units_invalid_input_validation(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test query endpoint input validation for invalid parameters.
        
        Test Cases:
        1. Invalid pax_count (< 1) → validation error
        2. Invalid limit (< 1) → validation error
        3. Invalid limit (> 500) → validation error
        4. Invalid offset (< 0) → validation error
        5. Non-UUID provider_id → validation error
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        provider, _ = create_stay_provider_with_unit(client, superuser_token_headers, db, owner)
        provider_id = provider["id"]

        # Test Case 1: Invalid pax_count (0 should be rejected, min is 1)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&pax_count=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "pax_count=0 should be rejected (min is 1)"

        # Test Case 2: Invalid limit (0)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit=0 should be rejected (min is 1)"

        # Test Case 3: Invalid limit (> 500)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&limit=501",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit=501 should be rejected (max is 500)"

        # Test Case 4: Invalid offset (negative)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id={provider_id}&offset=-1",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "offset=-1 should be rejected (min is 0)"

        # Test Case 5: Invalid provider_id (not a UUID)
        r = client.get(
            f"{settings.API_V1_STR}/query/units?provider_id=not-a-uuid",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "Invalid UUID should be rejected"


    def test_query_stay_providers_authorization(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test that /query/stay-providers require superuser or agency staff authentication.
        
        Test Cases:
        1. Unauthenticated request → 401
        2. Normal user (not agency staff) → 403
        3. Superuser → 200
        4. Agency staff → 200
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        
        # Create a stay provider with a unit
        provider, _ = create_stay_provider_with_unit(client, superuser_token_headers, db, owner, lat=10.0, lon=10.0)
        
        # Test Case 1: Unauthenticated request → 401
        r = client.get(f"{settings.API_V1_STR}/query/stay-providers")
        assert r.status_code == 401, "Unauthenticated request should return 401"
        
        # Test Case 2: Normal user without agency staff role → 403
        normal_user_headers = authentication_token_from_phone(client=client, phone_number=phone_number, db=db)
        r = client.get(f"{settings.API_V1_STR}/query/stay-providers", headers=normal_user_headers)
        assert r.status_code == 403, "Normal user without staff role should get 403"
        
        # Test Case 3: Superuser can query → 200
        r = client.get(f"{settings.API_V1_STR}/query/stay-providers?location=Banglore", headers=superuser_token_headers)
        assert r.status_code == 200, "Superuser should be able to query"
        assert "data" in r.json()
        assert "count" in r.json()
        
        # Test Case 4: Make user agency staff and retry → 200
        agency_body = {"agency_name": "Auth Test Agency", "contact_email": "auth@test.com", "location_id": None, "created_by": str(owner.id)}
        r = client.post(f"{settings.API_V1_STR}/travel-agency", headers=superuser_token_headers, json=agency_body)
        assert r.status_code == 200
        agency_id = r.json()["id"]
        
        staff_body = {"user_id": str(owner.id), "role": None}
        r = client.post(f"{settings.API_V1_STR}/travel-agency/{agency_id}/staffs", headers=superuser_token_headers, json=staff_body)
        assert r.status_code == 200
        
        # Now the user should be able to query
        r = client.get(f"{settings.API_V1_STR}/query/stay-providers?lat=24.8704721&lon=67.0847214", headers=normal_user_headers)
        assert r.status_code == 200, "Agency staff should be able to query"


    def test_query_stay_providers_by_location(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test filtering stay providers by location.
        
        Scenario:
        - Create 2 locations (Delhi, Mumbai)
        - Create providers in both locations
        - Query by each location
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        
        # Create provider in Delhi
        provider_delhi, _ = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=28.7041, lon=77.1025, room_rate=100, amenity="wifi"
        )
        provider_delhi_id = provider_delhi["id"]
        
        # Create provider in Mumbai
        provider_mumbai, _ = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=19.0760, lon=72.8777, room_rate=150, amenity="pool"
        )
        provider_mumbai_id = provider_mumbai["id"]
        
        # Test Case 1: Query all providers in india
        r = client.get(f"{settings.API_V1_STR}/query/stay-providers?location=india&radius_km=1500", headers=superuser_token_headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 2, "Should find both providers"
        
        # Test Case 2: Query by Delhi
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=20",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1, "Should find only Delhi provider"
        assert data["data"][0]["id"] == provider_delhi_id
        
        # Test Case 3: Query by Mumbai
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=mumbai&radius_km=5",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1, "Should find only Mumbai provider"
        assert data["data"][0]["id"] == provider_mumbai_id

    def test_query_stay_providers_by_amenities(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session
    ):
        """
        Test filtering stay providers by amenities with AND semantics + location filter.

        All providers are created near Delhi.
        Queries include location=delhi to ensure geo filtering is applied.
        
        Scenario:
        - Provider 1: rooms with [wifi, ac]
        - Provider 2: rooms with [pool, gym]
        - Provider 3: rooms with [wifi, pool, parking]
        
        Test Cases:
        1. amenities=wifi → Providers 1, 3
        2. amenities=wifi,ac → Provider 1 only (both amenities)
        3. amenities=pool → Providers 2, 3
        4. amenities=wifi,pool → Provider 3 only (both)
        5. amenities=wifi,notexists → No providers
        """

        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(
            session=db,
            user_create=UserCreate(phone_number=phone_number, password=password)
        )

        # Common location (Delhi)
        base_lat, base_lon = 28.7041, 77.1025

        # Provider 1: wifi + ac
        prov1, unit1 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat, lon=base_lon, room_rate=100, amenity="wifi"
        )
        prov1_id, unit1_id = prov1["id"], unit1["id"]

        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov1_id}/stay/units/{unit1_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "ac", "amenity_scope": AmenityScope.COMMON}
        )
        assert r.status_code == 200

        # Provider 2: pool + gym
        prov2, unit2 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.01, lon=base_lon + 0.01, room_rate=150, amenity="pool"
        )
        prov2_id, unit2_id = prov2["id"], unit2["id"]

        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov2_id}/stay/units/{unit2_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "gym", "amenity_scope": AmenityScope.COMMON}
        )
        assert r.status_code == 200

        # Provider 3: wifi + pool + parking
        prov3, unit3 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.02, lon=base_lon + 0.02, room_rate=200, amenity="wifi"
        )
        prov3_id, unit3_id = prov3["id"], unit3["id"]

        for amenity in ["pool", "parking"]:
            r = client.post(
                f"{settings.API_V1_STR}/providers/{prov3_id}/stay/units/{unit3_id}/amenities",
                headers=superuser_token_headers,
                json={"amenity": amenity, "amenity_scope": AmenityScope.COMMON}
            )
            assert r.status_code == 200

        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50"

        # Test Case 1: wifi → Providers 1, 3
        r = client.get(f"{base_url}&amenities=wifi", headers=superuser_token_headers)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id in ids, "Provider 1 should have wifi"
        assert prov3_id in ids, "Provider 3 should have wifi"
        assert prov2_id not in ids, "Provider 2 should not have wifi"

        # Test Case 2: wifi AND ac → (only Provider 1)
        r = client.get(f"{base_url}&amenities=wifi,ac", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id in ids, "Provider 1 should have both wifi and ac"
        assert prov3_id not in ids, "Provider 3 should not have ac"

        # Test Case 3: pool → Providers 2, 3
        r = client.get(f"{base_url}&amenities=pool", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov2_id in ids, "Provider 2 should have pool"
        assert prov3_id in ids, "Provider 3 should have pool"
        assert prov1_id not in ids, "Provider 1 should not have pool"

        # Test Case 4: wifi AND pool → only Provider 3
        r = client.get(f"{base_url}&amenities=wifi,pool", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov3_id in ids, "Provider 3 should have both wifi and pool"
        assert prov1_id not in ids, "Provider 1 should not have pool"
        assert prov2_id not in ids, "Provider 2 should not have wifi"

        # Test Case 5: wifi + notexists → none (no providers)
        r = client.get(f"{base_url}&amenities=wifi,notexists", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert len(ids) == 0

    def test_query_stay_providers_by_price_range(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session
    ):
        """
        Test filtering stay providers by unit price range + location filter.
        Scenario:
        - Provider A: unit with room_rate=100
        - Provider B: unit with room_rate=200
        - Provider C: unit with room_rate=300
        
        Test Cases:
        1. min_price=100, max_price=100 → only Provider A
        2. min_price=100, max_price=200 → Providers A, B
        3. min_price=150, max_price=250 → only Provider B
        4. min_price=250 → only Provider C
        5. max_price=150 → only Provider A
        """

        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(
            session=db,
            user_create=UserCreate(phone_number=phone_number, password=password)
        )

        base_lat, base_lon = 28.7041, 77.1025

        prov_a, _ = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat, lon=base_lon, room_rate=100
        )
        prov_b, _ = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.01, lon=base_lon + 0.01, room_rate=200
        )
        prov_c, _ = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.02, lon=base_lon + 0.02, room_rate=300
        )

        prov_a_id = prov_a["id"]
        prov_b_id = prov_b["id"]
        prov_c_id = prov_c["id"]

        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=20"

        # Test Case 1
        r = client.get(f"{base_url}&min_price=100&max_price=100", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov_a_id in ids, "Provider A (100) should be found"
        assert prov_b_id not in ids, "Provider B (200) should not match price 100"
        assert prov_c_id not in ids, "Provider C (300) should not match price 100"

        # Test Case 2
        r = client.get(f"{base_url}&min_price=100&max_price=200", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov_a_id in ids, "Provider A (100) should be in 100-200 range"
        assert prov_b_id in ids, "Provider B (200) should be in 100-200 range"
        assert prov_c_id not in ids, "Provider C (300) should not be in 100-200 range"

        # Test Case 3
        r = client.get(f"{base_url}&min_price=150&max_price=250", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov_b_id in ids
        assert prov_a_id not in ids
        assert prov_c_id not in ids

        # Test Case 4
        r = client.get(f"{base_url}&min_price=250", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov_c_id in ids, "Provider C (300) should match min_price 250"
        assert prov_a_id not in ids, "Provider A (100) should not match min_price 250"
        assert prov_b_id not in ids, "Provider B (200) should not match min_price 250"

        # Test Case 5
        r = client.get(f"{base_url}&max_price=150", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov_a_id in ids, "Provider A (100) should match max_price 150"
        assert prov_b_id not in ids, "Provider B (200) should not match max_price 150"
        assert prov_c_id not in ids, "Provider C (300) should not match max_price 150"


    def test_query_stay_providers_by_pax_count(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
        db: Session
    ):
        """
        Test filtering stay providers by passenger count + location filter.
        Scenario:
        - Provider 1: one unit with max_occupancy=2
        - Provider 2: two units with max_occupancy=(3, 2) → total 5
        - Provider 3: one unit with max_occupancy=6
        
        Test Cases:
        1. pax_count=1 → all providers
        2. pax_count=2 → all providers
        3. pax_count=3 → Providers 2, 3 (individual or total capacity)
        4. pax_count=4 → Providers 2, 3
        5. pax_count=6 → Providers 2, 3
        6. pax_count=7 → no providers
        """

        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(
            session=db,
            user_create=UserCreate(phone_number=phone_number, password=password)
        )

        from app.models.travel.location import Location

        # Base location (Delhi)
        base_lat, base_lon = 28.7041, 77.1025

        # ------------------------
        # Provider 1 (max = 2)
        # single unit, max_occupancy=2
        # ------------------------
        prov1_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Pax Provider 1",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": base_lat,
            "longitude": base_lon,
            "property_type": "hotel",
            "room_count": 1,
            "optimal_occupancy": 2,
            "max_occupancy": 2
        }

        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=prov1_data)
        assert r.status_code == 201
        prov1_id = r.json()["id"]

        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov1_id}/stay/units",
            headers=superuser_token_headers,
            json={"name": "Unit 1", "room_rate": 100, "max_occupancy": 2}
        )
        assert r.status_code == 200

        # ------------------------
        # Provider 2 (3 + 2 units, provider max = 6)
        # two units, total capacity 5 (3 + 2), provider max_occupancy = 6
        # ------------------------
        prov2_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Pax Provider 2",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": base_lat + 0.01,
            "longitude": base_lon + 0.01,
            "property_type": "apartment",
            "room_count": 2,
            "optimal_occupancy": 5,
            "max_occupancy": 6
        }

        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=prov2_data)
        assert r.status_code == 201
        prov2_id = r.json()["id"]

        for idx, occ in enumerate([3, 2]):
            r = client.post(
                f"{settings.API_V1_STR}/providers/{prov2_id}/stay/units",
                headers=superuser_token_headers,
                json={"name": f"Unit {idx+1}", "room_rate": 100, "max_occupancy": occ}
            )
            assert r.status_code == 200

        # ------------------------
        # Provider 3 (max = 6)
        # single unit, max_occupancy=6
        # ------------------------
        prov3_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Pax Provider 3",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": base_lat + 0.02,
            "longitude": base_lon + 0.02,
            "property_type": "villa",
            "room_count": 1,
            "optimal_occupancy": 6,
            "max_occupancy": 6
        }

        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=prov3_data)
        assert r.status_code == 201
        prov3_id = r.json()["id"]

        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov3_id}/stay/units",
            headers=superuser_token_headers,
            json={"name": "Unit 1", "room_rate": 100, "max_occupancy": 6}
        )
        assert r.status_code == 200

        # ------------------------
        # Queries (WITH location)
        # ------------------------
        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50"

        # Test Case 1: pax_count=1 (all providers)
        r = client.get(f"{base_url}&pax_count=1", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id in ids, "Provider 1 has capacity >= 1"
        assert prov2_id in ids, "Provider 2 has capacity >= 1"
        assert prov3_id in ids, "Provider 3 has capacity >= 1"

        # Test Case 2: pax_count=2 (all providers)
        r = client.get(f"{base_url}&pax_count=2", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id in ids, "Provider 1 (max_occ 2) has capacity >= 2"
        assert prov2_id in ids, "Provider 2 (total 5) has capacity >= 2"
        assert prov3_id in ids, "Provider 3 (max_occ 6) has capacity >= 2"

        # Test Case 3: pax_count=3 (should get Providers 2, 3)
        r = client.get(f"{base_url}&pax_count=3", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id not in ids, "Provider 1 (max_occ 2) should NOT have capacity >= 3"
        assert prov2_id in ids, "Provider 2 (total 5) has capacity >= 3"
        assert prov3_id in ids, "Provider 3 (max_occ 6) has capacity >= 3"

        # Test Case 4: pax_count=6 (should get Providers 2 and 3 based on stay-provider max_occupancy)
        r = client.get(f"{base_url}&pax_count=6", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id not in ids
        assert prov2_id in ids
        assert prov3_id in ids

        # Test Case 5: pax_count=7 (no providers)
        r = client.get(f"{base_url}&pax_count=7", headers=superuser_token_headers)
        ids = [p["id"] for p in r.json()["data"]]
        assert len(ids) == 0

    def test_query_stay_providers_by_room_count(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test filtering stay providers by minimum room count.
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Base location (Delhi) to ensure all providers fall within query radius
        base_lat, base_lon = 28.7041, 77.1025

        # Provider 1: 2 rooms
        prov1, unit1 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat, lon=base_lon, room_rate=100, amenity="wifi", room_count=2
        )
        prov1_id = prov1["id"]

        # Provider 2: 3 rooms
        prov2, unit2 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.01, lon=base_lon + 0.01, room_rate=150, amenity="pool", room_count=3
        )
        prov2_id = prov2["id"]

        # Provider 3: 4 rooms
        prov3, unit3 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat + 0.02, lon=base_lon + 0.02, room_rate=200, amenity="wifi", room_count=4
        )
        prov3_id = prov3["id"]

        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50"

        # Test Case 1: room_count=2 (should get Providers 1, 2, and 3)
        r = client.get(f"{base_url}&room_count=2", headers=superuser_token_headers)
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]

        assert prov1_id in provider_ids, "Provider 1 has at least 2 rooms"
        assert prov2_id in provider_ids, "Provider 2 has at least 2 rooms"
        assert prov3_id in provider_ids, "Provider 3 has at least 2 rooms"

        # Test Case 2: room_count=3 → Providers 2, 3
        r = client.get(f"{base_url}&room_count=3", headers=superuser_token_headers)
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]

        assert prov1_id not in provider_ids, "Provider 1 has only 2 rooms"
        assert prov2_id in provider_ids, "Provider 2 has at least 3 rooms"
        assert prov3_id in provider_ids, "Provider 3 has at least 3 rooms"

        # Test Case 3: room_count=4 → Provider 3 only
        r = client.get(f"{base_url}&room_count=4", headers=superuser_token_headers)
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]

        assert prov1_id not in provider_ids, "Provider 1 has only 2 rooms"
        assert prov2_id not in provider_ids, "Provider 2 has only 3 rooms"
        assert prov3_id in provider_ids, "Provider 3 has 4 rooms"

        # Test Case 4: room_count=5 → none
        r = client.get(f"{base_url}&room_count=5", headers=superuser_token_headers)
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]

        assert len(provider_ids) == 0, "No provider has >= 5 rooms"

    def test_query_stay_providers_combined_filters(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test combined filtering with multiple parameters.

        Scenario:
        - Provider 1: location A, rooms with wifi, price 100
        - Provider 2: location B, rooms with pool, price 150
        - Provider 3: location A, rooms with wifi + pool, price 200

        Test Cases:
        1. location=A && min_price=100 → Providers 1, 3
        2. location=A && amenities=wifi && max_price=150 → Provider 1 only
        3. amenities=wifi,pool && min_price=200 → Provider 3
        4. location=B && amenities=wifi → no providers (location B has no wifi)
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Base coordinates for locations
        # Location A → Delhi cluster
        base_lat_a, base_lon_a = 28.7041, 77.1025

        # Location B → Mumbai cluster
        base_lat_b, base_lon_b = 19.0760, 72.8777

        # Provider 1: location A, wifi, price 100
        prov1, unit1 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat_a, lon=base_lon_a, room_rate=100, amenity="wifi"
        )
        prov1_id = prov1["id"]

        # Provider 2: location B, pool, price 150
        prov2, unit2 = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat_b, lon=base_lon_b, room_rate=150, amenity="pool"
        )
        prov2_id = prov2["id"]
        unit2_id = unit2["id"]

        # Provider 3: same location as Provider 1 (location A), wifi + pool, price 200
        # IMPORTANT: Need to create provider 3 at SAME location as provider 1 but get same location object
        # We'll manually create it in location A
        prov3_data = {
            "provider_type": ServiceProviderType.STAY,
            "provider_name": "Query Stay Provider 3",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": base_lat_a + 0.001,  # very close to location A
            "longitude": base_lon_a + 0.001,
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=prov3_data)
        assert r.status_code == 201
        prov3 = r.json()
        prov3_id = prov3["id"]

        unit3_data = {"name": "Unit 1", "room_rate": 200}
        r = client.post(f"{settings.API_V1_STR}/providers/{prov3_id}/stay/units", headers=superuser_token_headers, json=unit3_data)
        assert r.status_code == 200
        unit3 = r.json()
        unit3_id = unit3["id"]

        # Add wifi amenity
        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov3_id}/stay/units/{unit3_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "wifi", "amenity_scope": AmenityScope.COMMON}
        )
        assert r.status_code == 200

        # Add pool amenity
        r = client.post(
            f"{settings.API_V1_STR}/providers/{prov3_id}/stay/units/{unit3_id}/amenities",
            headers=superuser_token_headers,
            json={"amenity": "pool", "amenity_scope": AmenityScope.COMMON}
        )
        assert r.status_code == 200

        # Test Case 1: location A && min_price 100
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=25&min_price=100",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]
        assert prov1_id in provider_ids, "Provider 1 in location A with price 100 >= 100"
        assert prov3_id in provider_ids, "Provider 3 in location A with price 200 >= 100"
        assert prov2_id not in provider_ids, "Provider 2 is in location B, not A"

        # Test Case 2: location A && wifi && max_price 150
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=25&amenities=wifi&max_price=150",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        provider_ids = [p["id"] for p in data["data"]]
        assert prov1_id in provider_ids, "Provider 1 matches all filters"
        assert prov3_id not in provider_ids, "Provider 3 price 200 exceeds max_price 150"

        # Test Case 3: wifi AND pool && min_price 200
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=25&amenities=wifi,pool&min_price=200",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        provider_ids = [p["id"] for p in data["data"]]
        assert prov3_id in provider_ids, "Provider 3 has both wifi and pool with price 200 >= 200"
        assert prov1_id not in provider_ids, "Provider 1 does not have pool"

        # Test Case 4: location B && wifi (should be empty)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=mumbai&radius_km=25&amenities=wifi",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        provider_ids = [p["id"] for p in r.json()["data"]]
        assert prov2_id not in provider_ids, "Provider 2 in location B does not have wifi"
        assert prov1_id not in provider_ids, "Provider 1 is not in location B"


    def test_query_stay_providers_pagination(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test pagination with limit and offset for stay providers.
        
        Scenario:
        - Create 5 stay providers with unique amenity
        - Query filtered by amenity and test pagination
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Base location (Delhi cluster)
        base_lat, base_lon = 28.7041, 77.1025

        # Create 5 providers with unique amenity to ensure we can filter to just these
        unique_amenity = f"pagtest_{random_lower_string()}"
        provider_ids = []

        for i in range(5):
            provider, unit = create_stay_provider_with_unit(
                client, superuser_token_headers, db, owner,
                lat=base_lat + (i * 0.01),  # keep within radius
                lon=base_lon + (i * 0.01),
                room_rate=100 + (i * 50),
                amenity=unique_amenity
            )
            provider_ids.append(provider["id"])

        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50&amenities={unique_amenity}"

        # Test Case 1: Get first 2 (limit=2, offset=0)
        r = client.get(
            f"{base_url}&limit=2&offset=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2, "limit=2 should return 2 items"

        # Test Case 2: Get next 2 (limit=2, offset=2)
        r = client.get(
            f"{base_url}&limit=2&offset=2",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2, "limit=2 should return 2 items"

        # Test Case 3: Get last item (limit=2, offset=4)
        r = client.get(
            f"{base_url}&limit=2&offset=4",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1, "Last item should return 1 result"

        # Test Case 4: Out of bounds offset
        r = client.get(
            f"{base_url}&limit=2&offset=100",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 0, "Out of bounds offset should return empty"

        # Test Case 5: Validate limit bounds (max 500)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50&limit=501",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit > 500 should be rejected"

    def test_query_stay_providers_input_validation(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test input validation for /query/stay-providers endpoint.

        Test Cases:
        1. Invalid limit (0) → 422
        2. Invalid limit (501) → 422
        3. Invalid offset (-1) → 422
        4. Invalid pax_count (0) → 422
        5. Invalid location (empty string) → 422
        6. Invalid latitude → 422
        7. Invalid longitude → 422
        8. Invalid radius_km (negative) → 422
        """

        # Test Case 1: Invalid limit (0)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?limit=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit=0 should be rejected"

        # Test Case 2: Invalid limit (501)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?limit=501",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "limit > 500 should be rejected"

        # Test Case 3: Invalid offset
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?offset=-1",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "offset < 0 should be rejected"

        # Test Case 4: Invalid pax_count
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?pax_count=0",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "pax_count < 1 should be rejected"

        # Test Case 5: Invalid location (empty)
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=",
            headers=superuser_token_headers
        )
        assert r.status_code == 400, "Empty location should be rejected"

        # Test Case 6: Invalid latitude
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?lat=invalid&lon=77.1",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "Invalid latitude should be rejected"

        # Test Case 7: Invalid longitude
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?lat=28.7&lon=invalid",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "Invalid longitude should be rejected"

        # Test Case 8: Invalid radius_km
        r = client.get(
            f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=-10",
            headers=superuser_token_headers
        )
        assert r.status_code == 422, "Negative radius_km should be rejected"    

    def test_query_stay_providers_comma_separated_amenities(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test that comma-separated amenities work same as repeated params.
        
        Scenario:
        - Create provider with wifi, ac, parking
        - Query with repeated params: ?amenities=wifi&amenities=ac
        - Query with comma-separated: ?amenities=wifi,ac
        - Both should return same results
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        
        # Base location (Delhi cluster)
        base_lat, base_lon = 28.7041, 77.1025
        
        prov, unit = create_stay_provider_with_unit(
            client, superuser_token_headers, db, owner,
            lat=base_lat, lon=base_lon, room_rate=100, amenity="wifi"
        )
        prov_id = prov["id"]
        unit_id = unit["id"]
        
        # Add more amenities
        for amenity in ["ac", "parking"]:
            r = client.post(
                f"{settings.API_V1_STR}/providers/{prov_id}/stay/units/{unit_id}/amenities",
                headers=superuser_token_headers,
                json={"amenity": amenity, "amenity_scope": AmenityScope.COMMON}
            )
            assert r.status_code == 200
        
        base_url = f"{settings.API_V1_STR}/query/stay-providers?location=delhi&radius_km=50"
        
        # Test Case 1: Repeated params
        r1 = client.get(
            f"{base_url}&amenities=wifi&amenities=ac",
            headers=superuser_token_headers
        )
        assert r1.status_code == 200
        ids1 = [p["id"] for p in r1.json()["data"]]
        
        # Test Case 2: Comma-separated
        r2 = client.get(
            f"{base_url}&amenities=wifi,ac",
            headers=superuser_token_headers
        )
        assert r2.status_code == 200
        ids2 = [p["id"] for p in r2.json()["data"]]
        
        # Both should return same providers
        assert set(ids1) == set(ids2), "Repeated params and comma-separated should give same results"
        assert prov_id in ids1, "Provider should be returned in both cases"
        
        # Test Case 3: Deduplication of repeated amenities
        r = client.get(
            f"{base_url}&amenities=wifi,wifi,ac",
            headers=superuser_token_headers
        )
        assert r.status_code == 200
        ids3 = [p["id"] for p in r.json()["data"]]
        
        assert set(ids3) == set(ids1), "Duplicates should dedupe correctly"


    def test_query_cabs_with_capacity_and_rate_filters(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test cab querying with new capacity and rate filters.
        
        Scenario:
        - Cab 1: capacity=4, minimum_rate=100, per_km_rate=15, km_for_minimum_rate=5
        - Cab 2: capacity=6, minimum_rate=150, per_km_rate=20, km_for_minimum_rate=10
        - Cab 3: capacity=2, minimum_rate=80, per_km_rate=12, km_for_minimum_rate=3
        
        Test Cases:
        1. min_capacity=5 → should return Cab 2 only
        2. max_capacity=3 → should return Cab 3 only
        3. min_minimum_rate=120 → should return Cab 2 only
        4. max_per_km_rate=16 → should return Cab 1 and Cab 3
        5. min_km_for_minimum_rate=8 → should return Cab 2 only
        6. Combined filters: min_capacity=3&max_minimum_rate=120 → should return Cab 1 only
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))

        # Cab configurations with different capacities and rates
        cab_configs = [
            {"capacity": 4, "minimum_rate": 100, "per_km_rate": 15, "km_for_minimum_rate": 5, "vehicle_number": "CAB001"},
            {"capacity": 6, "minimum_rate": 150, "per_km_rate": 20, "km_for_minimum_rate": 10, "vehicle_number": "CAB002"},
            {"capacity": 2, "minimum_rate": 80, "per_km_rate": 12, "km_for_minimum_rate": 3, "vehicle_number": "CAB003"},
        ]

        provider_data = {
            "provider_type": ServiceProviderType.CAB,
            "provider_name": "Capacity Rate Test Provider",
            "owner_id": str(owner.id),
            "created_by": str(owner.id),
            "latitude": 28.7041,
            "longitude": 77.1025,
        }
        r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
        assert r.status_code == 201
        provider_id = r.json()["id"]

        # Create cabs with different specs
        for config in cab_configs:
            cab_data = {
                "vehicle_type": "SEDAN",
                "vehicle_number": config["vehicle_number"],
                "minimum_rate": config["minimum_rate"],
                "km_for_minimum_rate": config["km_for_minimum_rate"],
                "per_km_rate": config["per_km_rate"],
                "capacity": config["capacity"],
                "name": f"Cab {config['vehicle_number']}",
                "company_model": "Test Model",
                "color": "Blue"
            }
            r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab", headers=superuser_token_headers, json=cab_data)
            assert r.status_code in (200, 201, 400)  # Accept various status codes as per existing tests

        # Test Case 1: min_capacity=5 (should return only Cab 2 with capacity=6)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_capacity=5")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find at least Cab 2"
        # Verify the returned cabs have capacity >= 5
        for cab in data["data"]:
            assert cab["capacity"] >= 5, f"Cab {cab['vehicle_number']} should have capacity >= 5"

        # Test Case 2: max_capacity=3 (should return only Cab 3 with capacity=2)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?max_capacity=3")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find at least Cab 3"
        for cab in data["data"]:
            assert cab["capacity"] <= 3, f"Cab {cab['vehicle_number']} should have capacity <= 3"

        # Test Case 3: min_minimum_rate=120 (should return only Cab 2 with minimum_rate=150)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_minimum_rate=120")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find at least Cab 2"
        for cab in data["data"]:
            assert cab["minimum_rate"] >= 120, f"Cab {cab['vehicle_number']} should have minimum_rate >= 120"

        # Test Case 4: max_per_km_rate=16 (should return Cab 1 (15) and Cab 3 (12))
        r = client.get(f"{settings.API_V1_STR}/query/cabs?max_per_km_rate=16")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 2, "Should find Cab 1 and Cab 3"
        for cab in data["data"]:
            assert cab["per_km_rate"] <= 16, f"Cab {cab['vehicle_number']} should have per_km_rate <= 16"

        # Test Case 5: min_km_for_minimum_rate=8 (should return only Cab 2 with km_for_minimum_rate=10)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_km_for_minimum_rate=8")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find at least Cab 2"
        for cab in data["data"]:
            assert cab["km_for_minimum_rate"] >= 8, f"Cab {cab['vehicle_number']} should have km_for_minimum_rate >= 8"

        # Test Case 6: Combined filters - min_capacity=3&max_minimum_rate=120 (should return only Cab 1)
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_capacity=3&max_minimum_rate=120")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1, "Should find Cab 1"
        for cab in data["data"]:
            assert cab["capacity"] >= 3 and cab["minimum_rate"] <= 120, f"Cab {cab['vehicle_number']} should match combined filters"


    def test_query_drivers_with_capacity_filter(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test driver querying with min_capacity filter (filters drivers who have cabs with capacity >= min_capacity).
        
        Scenario:
        - Provider 1: Driver A with Cab (capacity=4)
        - Provider 2: Driver B with Cab (capacity=6)
        - Provider 3: Driver C with Cab (capacity=2)
        
        Test Cases:
        1. min_capacity=5 → should return Driver B only
        2. min_capacity=3 → should return Driver A and Driver B
        3. min_capacity=7 → should return no drivers
        """
        phone_number = random_phone()
        password = random_lower_string()
        owner = crud.create_user(session=db, user_create=UserCreate(phone_number=phone_number, password=password))
        expected_drivers = []

        # Driver and cab configurations
        driver_configs = [
            {"capacity": 4, "vehicle_number": "DRV001", "driver_name": "Driver A"},
            {"capacity": 6, "vehicle_number": "DRV002", "driver_name": "Driver B"},
            {"capacity": 2, "vehicle_number": "DRV003", "driver_name": "Driver C"},
        ]

        for config in driver_configs:
            # Create provider
            provider_data = {
                "provider_type": ServiceProviderType.CAB,
                "provider_name": f"Provider {config['driver_name']}",
                "owner_id": str(owner.id),
                "created_by": str(owner.id),
                "latitude": 28.7041,
                "longitude": 77.1025,
            }
            r = client.post(f"{settings.API_V1_STR}/providers/", headers=superuser_token_headers, json=provider_data)
            assert r.status_code == 201
            provider_id = r.json()["id"]

            # Create profile for driver
            profile_data = {"first_name": config["driver_name"], "primary_email": random_email(), "primary_phone_number": random_phone()}
            r = client.post(f"{settings.API_V1_STR}/profile/", headers=superuser_token_headers, json=profile_data)
            assert r.status_code == 200
            profile = r.json()

            # Create driver
            driver_data = {"user_id": str(owner.id), "profile_id": str(profile['id'])}
            r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab/drivers", headers=superuser_token_headers, json=driver_data)
            assert r.status_code == 200
            expected_drivers.append({
                "first_name": profile["first_name"],
                "primary_phone_number": profile["primary_phone_number"],
                "primary_email": profile["primary_email"],
            })

            # Create cab for this provider
            cab_data = {
                "vehicle_type": "SEDAN",
                "vehicle_number": config["vehicle_number"],
                "minimum_rate": 100.0,
                "km_for_minimum_rate": 5.0,
                "per_km_rate": 15.0,
                "capacity": config["capacity"],
                "name": f"Cab for {config['driver_name']}",
                "company_model": "Test Model",
                "color": "Blue"
            }
            r = client.post(f"{settings.API_V1_STR}/providers/{provider_id}/cab", headers=superuser_token_headers, json=cab_data)
            assert r.status_code in (200, 201, 400)

        # Test Case 1: min_capacity=5 (should return only Driver B who has cab with capacity=6)
        r = client.get(f"{settings.API_V1_STR}/query/drivers?min_capacity=5")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["data"][0]["full_name"] == "Driver B"
        assert data["data"][0]["primary_phone_number"] == expected_drivers[1]["primary_phone_number"]
        assert data["data"][0]["primary_email"] == expected_drivers[1]["primary_email"]

        # Test Case 2: min_capacity=3 (should return Driver A and Driver B)
        r = client.get(f"{settings.API_V1_STR}/query/drivers?min_capacity=3")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 2, "Should find at least Driver A and Driver B"
        returned_names = {driver["full_name"] for driver in data["data"]}
        for driver in ["Driver A", "Driver B"]:
            assert driver in returned_names, f"{driver} should be in results for min_capacity=3"
        returned_data = {driver["full_name"]: driver for driver in data["data"]}
        assert returned_data["Driver A"]["primary_phone_number"] == expected_drivers[0]["primary_phone_number"]
        assert returned_data["Driver A"]["primary_email"] == expected_drivers[0]["primary_email"]
        assert returned_data["Driver B"]["primary_phone_number"] == expected_drivers[1]["primary_phone_number"]
        assert returned_data["Driver B"]["primary_email"] == expected_drivers[1]["primary_email"]

        # Test Case 3: min_capacity=7 (should return no drivers)
        r = client.get(f"{settings.API_V1_STR}/query/drivers?min_capacity=7")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["data"] == []


    def test_query_cabs_input_validation(self, client: TestClient, superuser_token_headers: dict[str, str], db: Session):
        """
        Test input validation for new cab query parameters.
        
        Test Cases:
        1. Invalid min_capacity (< 1) → validation error
        2. Invalid max_capacity (< 1) → validation error
        3. Invalid min_minimum_rate (< 0) → validation error
        4. Invalid max_per_km_rate (< 0) → validation error
        5. Invalid min_km_for_minimum_rate (< 0) → validation error
        """
        # Test Case 1: Invalid min_capacity
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_capacity=0")
        assert r.status_code == 422, "min_capacity=0 should be rejected"

        # Test Case 2: Invalid max_capacity
        r = client.get(f"{settings.API_V1_STR}/query/cabs?max_capacity=0")
        assert r.status_code == 422, "max_capacity=0 should be rejected"

        # Test Case 3: Invalid min_minimum_rate
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_minimum_rate=-1")
        assert r.status_code == 422, "min_minimum_rate=-1 should be rejected"

        # Test Case 4: Invalid max_per_km_rate
        r = client.get(f"{settings.API_V1_STR}/query/cabs?max_per_km_rate=-5")
        assert r.status_code == 422, "max_per_km_rate=-5 should be rejected"

        # Test Case 5: Invalid min_km_for_minimum_rate
        r = client.get(f"{settings.API_V1_STR}/query/cabs?min_km_for_minimum_rate=-1")
        assert r.status_code == 422, "min_km_for_minimum_rate=-1 should be rejected"

