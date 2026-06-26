from datetime import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session


from app.core.config import settings
from tests.utils.test_helper import TestHelper

from app.models.travel.booking import Booking



class BookingTestHelper(TestHelper):
    def create_booking(
        self,
        client: TestClient,
        db: Session,
        staff_headers,
        traveller_profiles=None,
        total_amount=1000,
    ):
        traveller_profiles = traveller_profiles or []

        payload = {
            "date_starting_from": datetime.now().isoformat(),
            "date_ending_on": datetime.now().isoformat(),
            "total_amount": total_amount,
            "travellers": [
                {
                    "traveller_id": str(p.id)
                }
                for p in traveller_profiles
            ],
            "cabs": [],
            "stays": [],
        }

        response = client.post(
            f"{settings.API_V1_STR}/booking",
            headers=staff_headers,
            json=payload,
        )

        assert response.status_code == 200

        booking_id = response.json()["id"]

        booking = db.get(
            Booking,
            booking_id,
        )

        return booking
    

    def refresh_booking(self,db: Session,booking_id,) -> Booking:
        db.expire_all()

        booking = db.get(
            Booking,
            booking_id,
        )

        return booking


    def create_booking_context(
        self,
        client: TestClient,
        db: Session,
    ):
        owner, owner_headers, agency = self.create_agency(
            client,
            db,
        )

        (
            staff_user,
            staff_headers,
            staff,
        ) = self.create_staff(
            client,
            db,
            agency,
        )

        traveller_user, _ = self.create_user_with_token(
            client,
            db,
        )

        traveller_profile = self.create_profile(
            db,
            traveller_user,
        )

        booking = self.create_booking(
            client,
            db,
            staff_headers,
            [traveller_profile],
        )

        db.refresh(booking)

        return {
            "owner": owner,
            "owner_headers": owner_headers,

            "agency": agency,

            "staff_user": staff_user,
            "staff_headers": staff_headers,
            "staff": staff,

            "traveller_profile": traveller_profile,

            "booking": booking,
        }
    

    def create_second_booking_context(
        self,
        client,
        db,
    ):
        """
        Used for cross-booking attacks.
        """
        return self.create_booking_context(
            client,
            db,
        )
    

    def first_booking_traveller(
        self,
        db,
        booking,
    ):
        db.refresh(booking)

        return booking.travellers[0]
    






