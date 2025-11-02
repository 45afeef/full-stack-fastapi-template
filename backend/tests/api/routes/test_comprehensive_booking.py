import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models.user.profile import Profile
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email, random_lower_string


class TestBookingFull:
    def test_staff_cannot_set_other_agency_id_on_create(self, client: TestClient, db: Session) -> None:
        """A staff user cannot impersonate another agency by setting travel_agency_id to another agency; the booking should be attached to the staff's agency."""
        # create owners and two agencies
        owner1_email = random_email()
        owner1_headers = authentication_token_from_email(client=client, email=owner1_email, db=db)
        owner1 = crud.get_user_by_email(session=db, email=owner1_email)

        owner2_email = random_email()
        owner2_headers = authentication_token_from_email(client=client, email=owner2_email, db=db)
        owner2 = crud.get_user_by_email(session=db, email=owner2_email)

        agency_a = crud.create_travel_agency(session=db, agency={"agency_name": "A", "created_by": str(owner1.id)})
        agency_b = crud.create_travel_agency(session=db, agency={"agency_name": "B", "created_by": str(owner2.id)})

        # create staff for agency A
        staff_email = random_email()
        staff_headers = authentication_token_from_email(client=client, email=staff_email, db=db)
        staff_user = crud.get_user_by_email(session=db, email=staff_email)
        staff = crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency_a.id)})

        # create traveller profile
        traveller_email = random_email()
        traveller_headers = authentication_token_from_email(client=client, email=traveller_email, db=db)
        traveller_user = crud.get_user_by_email(session=db, email=traveller_email)
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
        owner_email = random_email()
        owner_headers = authentication_token_from_email(client=client, email=owner_email, db=db)
        owner = crud.get_user_by_email(session=db, email=owner_email)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "Test", "created_by": str(owner.id)})

        staff_email = random_email()
        staff_headers = authentication_token_from_email(client=client, email=staff_email, db=db)
        staff_user = crud.get_user_by_email(session=db, email=staff_email)
        crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        payload = {"booking_date": datetime.utcnow().isoformat(), "total_amount": 100}
        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=payload)
        assert r.status_code == 422

    def test_create_booking_with_unknown_traveller_in_travellers_returns_404(self, client: TestClient, db: Session) -> None:
        """If one of the nested travellers references a non-existent profile, API should return 404 and not create the booking."""
        owner_email = random_email()
        owner_headers = authentication_token_from_email(client=client, email=owner_email, db=db)
        owner = crud.get_user_by_email(session=db, email=owner_email)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "Test2", "created_by": str(owner.id)})

        staff_email = random_email()
        staff_headers = authentication_token_from_email(client=client, email=staff_email, db=db)
        staff_user = crud.get_user_by_email(session=db, email=staff_email)
        crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        # create valid top-level traveler profile
        traveller_email = random_email()
        traveller_headers = authentication_token_from_email(client=client, email=traveller_email, db=db)
        traveller_user = crud.get_user_by_email(session=db, email=traveller_email)
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
        owner1_email = random_email()
        owner1_headers = authentication_token_from_email(client=client, email=owner1_email, db=db)
        owner1 = crud.get_user_by_email(session=db, email=owner1_email)
        agency1 = crud.create_travel_agency(session=db, agency={"agency_name": "One", "created_by": str(owner1.id)})

        owner2_email = random_email()
        owner2_headers = authentication_token_from_email(client=client, email=owner2_email, db=db)
        owner2 = crud.get_user_by_email(session=db, email=owner2_email)
        agency2 = crud.create_travel_agency(session=db, agency={"agency_name": "Two", "created_by": str(owner2.id)})

        # staff1
        staff1_email = random_email()
        staff1_headers = authentication_token_from_email(client=client, email=staff1_email, db=db)
        staff1_user = crud.get_user_by_email(session=db, email=staff1_email)
        staff1 = crud.assign_agency_staff(session=db, staff={"user_id": str(staff1_user.id), "travel_agency_id": str(agency1.id)})

        # staff2
        staff2_email = random_email()
        staff2_headers = authentication_token_from_email(client=client, email=staff2_email, db=db)
        staff2_user = crud.get_user_by_email(session=db, email=staff2_email)
        staff2 = crud.assign_agency_staff(session=db, staff={"user_id": str(staff2_user.id), "travel_agency_id": str(agency2.id)})

        # create traveller profile
        traveller_email = random_email()
        traveller_headers = authentication_token_from_email(client=client, email=traveller_email, db=db)
        traveller_user = crud.get_user_by_email(session=db, email=traveller_email)
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
        owner_email = random_email()
        owner_headers = authentication_token_from_email(client=client, email=owner_email, db=db)
        owner = crud.get_user_by_email(session=db, email=owner_email)
        agency = crud.create_travel_agency(session=db, agency={"agency_name": "OwnerTest", "created_by": str(owner.id)})

        # staff
        staff_email = random_email()
        staff_headers = authentication_token_from_email(client=client, email=staff_email, db=db)
        staff_user = crud.get_user_by_email(session=db, email=staff_email)
        staff = crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        # another staff from different agency
        other_owner_email = random_email()
        authentication_token_from_email(client=client, email=other_owner_email, db=db)
        other_owner = crud.get_user_by_email(session=db, email=other_owner_email)
        other_agency = crud.create_travel_agency(session=db, agency={"agency_name": "Other", "created_by": str(other_owner.id)})
        other_staff_email = random_email()
        other_staff_headers = authentication_token_from_email(client=client, email=other_staff_email, db=db)
        other_staff_user = crud.get_user_by_email(session=db, email=other_staff_email)
        crud.assign_agency_staff(session=db, staff={"user_id": str(other_staff_user.id), "travel_agency_id": str(other_agency.id)})

        # traveller
        traveller_email = random_email()
        traveller_headers = authentication_token_from_email(client=client, email=traveller_email, db=db)
        traveller_user = crud.get_user_by_email(session=db, email=traveller_email)
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
