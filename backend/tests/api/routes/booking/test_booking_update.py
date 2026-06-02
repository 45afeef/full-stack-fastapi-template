from tests.utils.booking_helper import BookingTestHelper

from app.core.config import settings

class TestBookingUpdateAuthorization(BookingTestHelper):

    def test_superuser_can_update_any_booking(self,client,db,superuser_token_headers):
        ctx = self.create_booking_context(client, db)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=superuser_token_headers,
            json={
                "status": "CONFIRMED",
            },
        )

        assert r.status_code == 200
        assert r.json()["status"] == "CONFIRMED"

    
    def test_staff_cannot_update_other_staff_booking(self,client,db):
        victim = self.create_booking_context(client, db)

        attacker = self.create_booking_context(client, db)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{victim['booking'].id}",
            headers=attacker["staff_headers"],
            json={
                "status": "CONFIRMED",
            },
        )

        assert r.status_code == 403


    def test_non_staff_cannot_update_booking(self,client,db,normal_user_token_headers):
        ctx = self.create_booking_context(client, db)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=normal_user_token_headers,
            json={
                "status": "CONFIRMED",
            },
        )

        assert r.status_code == 403


class TestBookingUpdateImmutableFields(BookingTestHelper):
    
    def test_cannot_change_travel_agency(self,client,db):
        ctx = self.create_booking_context(client, db)

        _, _, other_agency = self.create_agency(client,db,"Other Agency")

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travel_agency_id": str(other_agency.id),
            },
        )

        assert r.status_code == 200

        db.refresh(ctx["booking"])

        assert (ctx["booking"].travel_agency_id == ctx["agency"].id)


    def test_cannot_change_staff_owner(self,client,db):
        ctx = self.create_booking_context(client, db)

        _, _, other_staff = self.create_staff(
            client,
            db,
            ctx["agency"],
        )

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travel_agency_staff_id": str(other_staff.id),
            },
        )

        assert r.status_code == 200

        db.refresh(ctx["booking"])

        assert (
            ctx["booking"].travel_agency_staff_id
            == ctx["staff"].id
        )


class TestBookingTravellerSynchronization(BookingTestHelper):
    
    def test_omit_travellers_keeps_existing(self,client,db):
        ctx = self.create_booking_context(client, db)

        before = len(ctx["booking"].travellers)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "status": "CONFIRMED",
            },
        )

        assert r.status_code == 200

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        assert len(booking.travellers) == before


    def test_empty_travellers_removes_all(self,client,db):
        ctx = self.create_booking_context(client, db)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travellers": [],
            },
        )

        assert r.status_code == 200

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        assert len(booking.travellers) == 0


    def test_add_new_traveller(self,client,db):
        ctx = self.create_booking_context(client, db)

        relation = ctx["booking"].travellers[0]


        traveller_user, _ = self.create_user_with_token(client,db)
        new_profile = self.create_profile(db,traveller_user)


        second_traveller_user, _ = self.create_user_with_token(client,db)
        second_profile = self.create_profile(db,second_traveller_user)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travellers": [
                    {
                        "id": str(relation.id),
                    },
                    {
                        "traveller_id": str(new_profile.id),
                    },
                    {
                        "traveller_id": str(second_profile.id),
                    },
                ]
            },
        )

        assert r.status_code == 200

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        assert len(booking.travellers) == 2


    def test_remove_omitted_traveller(
        self,
        client,
        db,
    ):
        ctx = self.create_booking_context(client, db)

        relation = ctx["booking"].travellers[0]

        traveller_user, _ = self.create_user_with_token(
            client,
            db,
        )

        profile2 = self.create_profile(
            db,
            traveller_user,
        )

        client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travellers": [
                    {"id": str(relation.id)},
                    {"traveller_id": str(profile2.id)},
                ]
            },
        )

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        second_relation = next(
            t for t in booking.travellers
            if t.id != relation.id
        )

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "travellers": [
                    {"id": str(relation.id)},
                ]
            },
        )

        assert r.status_code == 200

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        ids = {str(x.id) for x in booking.travellers}

        assert str(relation.id) in ids
        assert str(second_relation.id) not in ids


    def test_traveller_relation_must_belong_to_booking(
        self,
        client,
        db,
    ):
        booking_a = self.create_booking_context(
            client,
            db,
        )

        booking_b = self.create_booking_context(
            client,
            db,
        )

        foreign_relation = (
            booking_b["booking"]
            .travellers[0]
            .id
        )

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{booking_a['booking'].id}",
            headers=booking_a["staff_headers"],
            json={
                "travellers": [
                    {
                        "id": str(foreign_relation),
                    }
                ]
            },
        )

        assert r.status_code == 400


class TestBookingUpdateTransactions(BookingTestHelper):

    def test_rollback_on_invalid_traveller(self,client,db):
        ctx = self.create_booking_context(client, db)

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "status": "CONFIRMED",
                "travellers": [
                    {
                        "traveller_id": str(self.fake_uuid()),
                    }
                ],
            },
        )

        assert r.status_code == 404

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        assert booking.status != "CONFIRMED"


    def test_mixed_rollback_on_invalid_cab(self,client,db):
        ctx = self.create_booking_context(client, db)

        existing_relation = (
            ctx["booking"].travellers[0]
        )

        r = client.patch(
            f"{settings.API_V1_STR}/booking/{ctx['booking'].id}",
            headers=ctx["staff_headers"],
            json={
                "status": "CONFIRMED",
                "travellers": [
                    {
                        "id": str(existing_relation.id),
                    }
                ],
                "cabs": [
                    {
                        "cab_id": str(self.fake_uuid()),
                    }
                ],
            },
        )

        assert r.status_code == 404

        booking = self.refresh_booking(
            db,
            ctx["booking"].id,
        )

        assert booking.status != "CONFIRMED"
        assert len(booking.travellers) == 1
        assert len(booking.cabs) == 0