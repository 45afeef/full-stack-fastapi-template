import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models.user.profile import Profile
from tests.utils.user import authentication_token_from_phone
from tests.utils.utils import random_phone, random_lower_string


class TestBookingFull:
    def test_staff_cannot_set_other_agency_id_on_create(self, client: TestClient, db: Session) -> None:
        """A staff user cannot impersonate another agency by setting travel_agency_id to another agency; the booking should be attached to the staff's agency."""
        # create owners and two agencies
        owner1_phone = random_phone()
        owner1_headers = authentication_token_from_phone(client=client, phone_number=owner1_phone, db=db)
        owner1 = crud.get_user_by_phone(session=db, phone_number=owner1_phone)

        owner2_phone = random_phone()
        owner2_headers = authentication_token_from_phone(client=client, phone_number=owner2_phone, db=db)
        owner2 = crud.get_user_by_phone(session=db, phone_number=owner2_phone)

        agency_a = crud.create_travel_agency(session=db, agency={"agency_name": "A", "created_by": str(owner1.id), "contact_email": random_lower_string()})
        agency_b = crud.create_travel_agency(session=db, agency={"agency_name": "B", "created_by": str(owner2.id), "contact_email": random_lower_string()})

        # create staff for agency A
        staff_phone = random_phone()
        staff_headers = authentication_token_from_phone(client=client, phone_number=staff_phone, db=db)
        staff_user = crud.get_user_by_phone(session=db, phone_number=staff_phone)
        staff = crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency_a.id)})

        # create traveller profile
        traveller_phone = random_phone()
        traveller_headers = authentication_token_from_phone(client=client, phone_number=traveller_phone, db=db)
        traveller_user = crud.get_user_by_phone(session=db, phone_number=traveller_phone)
        profile = Profile(user_id=traveller_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Try to create booking with travel_agency_id set to agency_b.id (different agency)
        booking_payload = {
            "traveler_id": str(profile.id),
            "booking_date": datetime.utcnow().isoformat(),
            "total_amount": 500,
            "travel_agency_id": str(agency_b.id),
            "travellers": [{"traveller_id": str(profile.id)}],
            "cabs": [],
            "stays": [],
        }

        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=booking_payload)
        assert r.status_code == 200
        created = r.json()
        # booking should be attached to agency A (staff's agency), not B
        assert created.get("travel_agency_id") == str(agency_a.id)

    def test_create_booking_missing_traveler_id_returns_422(self, client: TestClient, db: Session) -> None:
        """Missing top-level traveler_id should return 422."""
        # create owner + agency + staff
        owner_phone = random_phone()
        owner_headers = authentication_token_from_phone(client=client, phone_number=owner_phone, db=db)
        owner = crud.get_user_by_phone(session=db, phone_number=owner_phone)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "Test", "created_by": str(owner.id), "contact_email": random_lower_string()})

        staff_phone = random_phone()
        staff_headers = authentication_token_from_phone(client=client, phone_number=staff_phone, db=db)
        staff_user = crud.get_user_by_phone(session=db, phone_number=staff_phone)
        crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        payload = {"booking_date": datetime.utcnow().isoformat(), "total_amount": 100}
        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=payload)
        assert r.status_code == 422

    def test_create_booking_with_unknown_traveller_in_travellers_returns_404(self, client: TestClient, db: Session) -> None:
        """If one of the nested travellers references a non-existent profile, API should return 404 and not create the booking."""
        owner_phone = random_phone()
        owner_headers = authentication_token_from_phone(client=client, phone_number=owner_phone, db=db)
        owner = crud.get_user_by_phone(session=db, phone_number=owner_phone)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "Test2", "created_by": str(owner.id), "contact_email": random_lower_string()})

        staff_phone = random_phone()
        staff_headers = authentication_token_from_phone(client=client, phone_number=staff_phone, db=db)
        staff_user = crud.get_user_by_phone(session=db, phone_number=staff_phone)
        crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        # create valid top-level traveler profile
        traveller_phone = random_phone()
        traveller_headers = authentication_token_from_phone(client=client, phone_number=traveller_phone, db=db)
        traveller_user = crud.get_user_by_phone(session=db, phone_number=traveller_phone)
        profile = Profile(user_id=traveller_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # nested travellers contains a non-existent profile id
        bad_id = uuid.uuid4()
        booking_payload = {
            "traveler_id": str(profile.id),
            "booking_date": datetime.utcnow().isoformat(),
            "total_amount": 200,
            "travellers": [{"traveller_id": str(bad_id)}],
            "cabs": [],
            "stays": [],
        }

        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=booking_payload)
        assert r.status_code == 404
        assert f"Traveller profile {bad_id} not found" in r.text

    def test_staff_cannot_update_another_staff_booking(self, client: TestClient, db: Session) -> None:
        """Staff from one agency cannot update a booking created by staff from another agency."""
        # setup two agencies with staff
        owner1_phone = random_phone()
        owner1_headers = authentication_token_from_phone(client=client, phone_number=owner1_phone, db=db)
        owner1 = crud.get_user_by_phone(session=db, phone_number=owner1_phone)
        agency1 = crud.create_travel_agency(session=db, agency={"agency_name": "One", "created_by": str(owner1.id), "contact_email": random_lower_string()})

        owner2_phone = random_phone()
        owner2_headers = authentication_token_from_phone(client=client, phone_number=owner2_phone, db=db)
        owner2 = crud.get_user_by_phone(session=db, phone_number=owner2_phone)
        agency2 = crud.create_travel_agency(session=db, agency={"agency_name": "Two", "created_by": str(owner2.id), "contact_email": random_lower_string()})

        # staff1
        staff1_phone = random_phone()
        staff1_headers = authentication_token_from_phone(client=client, phone_number=staff1_phone, db=db)
        staff1_user = crud.get_user_by_phone(session=db, phone_number=staff1_phone)
        staff1 = crud.assign_agency_staff(session=db, staff={"user_id": str(staff1_user.id), "travel_agency_id": str(agency1.id)})

        # staff2
        staff2_phone = random_phone()
        staff2_headers = authentication_token_from_phone(client=client, phone_number=staff2_phone, db=db)
        staff2_user = crud.get_user_by_phone(session=db, phone_number=staff2_phone)
        staff2 = crud.assign_agency_staff(session=db, staff={"user_id": str(staff2_user.id), "travel_agency_id": str(agency2.id)})

        # create traveller profile
        traveller_phone = random_phone()
        traveller_headers = authentication_token_from_phone(client=client, phone_number=traveller_phone, db=db)
        traveller_user = crud.get_user_by_phone(session=db, phone_number=traveller_phone)
        profile = Profile(user_id=traveller_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # staff1 creates a booking
        booking_payload = {
            "traveler_id": str(profile.id),
            "booking_date": datetime.utcnow().isoformat(),
            "total_amount": 700,
            "travellers": [{"traveller_id": str(profile.id)}],
            "cabs": [],
            "stays": [],
        }
        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff1_headers, json=booking_payload)
        assert r.status_code == 200
        booking = r.json()

        # staff2 tries to update
        patch_payload = {"status": "CANCELLED"}
        r2 = client.patch(f"{settings.API_V1_STR}/booking/{booking['id']}", headers=staff2_headers, json=patch_payload)
        assert r2.status_code == 403

    def test_get_booking_permission_matrix(self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]) -> None:
        """Verify get booking permissions: owner, staff, other staff, superuser."""
        # owner + agency
        owner_phone = random_phone()
        owner_headers = authentication_token_from_phone(client=client, phone_number=owner_phone, db=db)
        owner = crud.get_user_by_phone(session=db, phone_number=owner_phone)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "OwnerTest", "created_by": str(owner.id), "contact_email": random_lower_string()})

        # assign owner as staff
        crud.assign_agency_staff(session=db, staff={"user_id": str(owner.id), "travel_agency_id": str(agency.id), "role": "OWNER"})

        # staff
        staff_phone = random_phone()
        staff_headers = authentication_token_from_phone(client=client, phone_number=staff_phone, db=db)
        staff_user = crud.get_user_by_phone(session=db, phone_number=staff_phone)
        staff = crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        # another staff from different agency
        other_owner_phone = random_phone()
        authentication_token_from_phone(client=client, phone_number=other_owner_phone, db=db)
        other_owner = crud.get_user_by_phone(session=db, phone_number=other_owner_phone)
        other_agency = crud.create_travel_agency(session=db, agency={"agency_name": "Other", "created_by": str(other_owner.id), "contact_email": random_lower_string()})
        other_staff_phone = random_phone()
        other_staff_headers = authentication_token_from_phone(client=client, phone_number=other_staff_phone, db=db)
        other_staff_user = crud.get_user_by_phone(session=db, phone_number=other_staff_phone)
        crud.assign_agency_staff(session=db, staff={"user_id": str(other_staff_user.id), "travel_agency_id": str(other_agency.id)})

        # traveller
        traveller_phone = random_phone()
        traveller_headers = authentication_token_from_phone(client=client, phone_number=traveller_phone, db=db)
        traveller_user = crud.get_user_by_phone(session=db, phone_number=traveller_phone)
        profile = Profile(user_id=traveller_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # staff creates booking
        booking_payload = {
            "traveler_id": str(profile.id),
            "booking_date": datetime.utcnow().isoformat(),
            "total_amount": 800,
            "travellers": [{"traveller_id": str(profile.id)}],
            "cabs": [],
            "stays": [],
        }
        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=booking_payload)
        assert r.status_code == 200
        booking = r.json()

        # staff can get own booking
        r1 = client.get(f"{settings.API_V1_STR}/booking/{booking['id']}", headers=staff_headers)
        assert r1.status_code == 200

        # other staff cannot
        r2 = client.get(f"{settings.API_V1_STR}/booking/{booking['id']}", headers=other_staff_headers)
        assert r2.status_code == 403

        # owner can get
        r3 = client.get(f"{settings.API_V1_STR}/booking/{booking['id']}", headers=owner_headers)
        assert r3.status_code == 200

        # superuser can get
        r4 = client.get(f"{settings.API_V1_STR}/booking/{booking['id']}", headers=superuser_token_headers)
        assert r4.status_code == 200


__all__ = ["TestBookingFull"]
