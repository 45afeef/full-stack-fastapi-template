from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app import crud
from app.core.security import verify_password
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_phone, random_lower_string


def test_create_user(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.phone_number == phone_number
    assert hasattr(user, "hashed_password")


def test_authenticate_user(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    authenticated_user = crud.authenticate(session=db, phone_number=phone_number, password=password)
    assert authenticated_user
    assert user.phone_number == authenticated_user.phone_number


def test_not_authenticate_user(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user = crud.authenticate(session=db, phone_number=phone_number, password=password)
    assert user is None


def test_check_if_user_is_active(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password, disabled=True)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_active


def test_check_if_user_is_superuser(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    phone_number = random_phone()
    password = random_lower_string()
    user_in = UserCreate(phone_number=phone_number, password=password)
    user = crud.create_user(session=db, user_create=user_in)
    assert user.is_superuser is False


def test_get_user(db: Session) -> None:
    password = random_lower_string()
    phone_number = random_phone()
    user_in = UserCreate(phone_number=phone_number, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.phone_number == user_2.phone_number
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    password = random_lower_string()
    phone_number = random_phone()
    user_in = UserCreate(phone_number=phone_number, password=password, is_superuser=True)
    user = crud.create_user(session=db, user_create=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    if user.id is not None:
        crud.update_user(session=db, db_user=user, user_in=user_in_update)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.phone_number == user_2.phone_number
    assert verify_password(new_password, user_2.hashed_password)
