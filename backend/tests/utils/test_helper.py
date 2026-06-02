from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session


from app import crud
from app.models.user.profile import Profile

from .utils import random_email, random_lower_string, random_phone
from .user import authentication_token_from_phone


class TestHelper:
    def create_user_with_token(
        self,
        client: TestClient,
        db: Session,
    ):
        phone = random_phone()

        headers = authentication_token_from_phone(
            client=client,
            phone_number=phone,
            db=db,
        )

        user = crud.get_user_by_phone(
            session=db,
            phone_number=phone,
        )

        return user, headers
    

    def create_profile(
        self,
        db: Session,
        user=None,
    ) -> Profile:

        profile = Profile(
            user_id=user.id if user else None,
        )

        db.add(profile)
        db.commit()
        db.refresh(profile)

        return profile
    
    
    def create_agency(
        self,
        client: TestClient,
        db: Session,
        name: str = "Agency",
    ):
        owner, owner_headers = self.create_user_with_token(
            client,
            db,
        )

        agency = crud.create_travel_agency(
            session=db,
            agency={
                "agency_name": name,
                "created_by": str(owner.id),
                "contact_email": random_email(),
            },
        )

        return owner, owner_headers, agency
    

    def create_staff(
        self,
        client: TestClient,
        db: Session,
        agency,
    ):
        user, headers = self.create_user_with_token(
            client,
            db,
        )

        staff = crud.assign_agency_staff(
            session=db,
            staff={
                "user_id": str(user.id),
                "travel_agency_id": str(agency.id),
            },
        )

        return user, headers, staff
    
    def fake_uuid(self):
        return str(uuid4())
