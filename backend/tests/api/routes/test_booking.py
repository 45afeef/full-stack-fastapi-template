import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from app.models.user.profile import Profile
from app.models.travel.providers import TravelAgency
from tests.utils.user import authentication_token_from_phone
from tests.utils.utils import random_phone, random_lower_string


class TestBookingRoutes:
    def test_staff_create_and_list_booking_success(
        self, client: TestClient, db: Session, superuser_token_headers: dict[str, str]
    ) -> None:
        # create owner and agency
        owner_phone = random_phone()
        owner_headers = authentication_token_from_phone(client=client, phone_number=owner_phone, db=db)
        owner = crud.get_user_by_phone(session=db, phone_number=owner_phone)

        agency_data = {"agency_name": "Test Agency", "created_by": str(owner.id), "contact_email": random_phone()}
        agency = crud.create_travel_agency(session=db, agency=agency_data)

        # create staff user and assign to agency
        staff_phone = random_phone()
        staff_headers = authentication_token_from_phone(client=client, phone_number=staff_phone, db=db)
        staff_user = crud.get_user_by_phone(session=db, phone_number=staff_phone)
        staff = crud.assign_agency_staff(session=db, staff={"user_id": str(staff_user.id), "travel_agency_id": str(agency.id)})

        # create traveller (profile)
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
            "total_amount": 12345,
            "travellers": [{"traveller_id": str(profile.id)}],
            "cabs": [],
            "stays": [],
        }

        r = client.post(f"{settings.API_V1_STR}/booking", headers=staff_headers, json=booking_payload)
        assert r.status_code == 200
        created = r.json()
        assert "id" in created
        booking_id = created["id"]

        # staff can list own bookings
        r = client.get(f"{settings.API_V1_STR}/booking", headers=staff_headers)
        assert r.status_code == 200
        data = r.json()
        # expect at least one booking
        assert any(b["id"] == booking_id for b in data)

        # owner can list bookings for agency
        r = client.get(f"{settings.API_V1_STR}/booking", headers=owner_headers)
        assert r.status_code == 200
        data_owner = r.json()
        assert any(b["id"] == booking_id for b in data_owner)

        # superuser can update booking status
        patch_payload = {"status": "CONFIRMED"}
        r = client.patch(f"{settings.API_V1_STR}/booking/{booking_id}", headers=superuser_token_headers, json=patch_payload)
        assert r.status_code == 200
        updated = r.json()
        assert updated.get("status") == "CONFIRMED"


    def test_non_staff_cannot_create_booking(self, client: TestClient, normal_user_token_headers: dict[str, str], db: Session) -> None:
        # create traveler
        traveller_phone = random_phone()
        traveller_headers = authentication_token_from_phone(client=client, phone_number=traveller_phone, db=db)
        traveller_user = crud.get_user_by_phone(session=db, phone_number=traveller_phone)
        profile = Profile()  # not linked to any user
        db.add(profile)
        db.commit()
        db.refresh(profile)

        booking_payload = {
            "traveler_id": str(profile.id),
            "booking_date": datetime.utcnow().isoformat(),
            "total_amount": 1000,
            "travellers": [{"traveller_id": str(profile.id)}],
            "cabs": [],
            "stays": [],
        }

        r = client.post(f"{settings.API_V1_STR}/booking", headers=normal_user_token_headers, json=booking_payload)
        assert r.status_code == 403
