from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_phone, random_lower_string


def user_authentication_headers(
    *, client: TestClient, phone_number: str, password: str
) -> dict[str, str]:
    data = {"username": phone_number, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(db: Session) -> User:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    return user


def authentication_token_from_phone(
    *, client: TestClient, phone_number: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given phone number.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.get_user_by_phone(session=db, phone_number=phone_number)
    if not user:
        user_in_create = UserCreate(phone_number=phone_number, password=password)
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, phone_number=phone_number, password=password)
