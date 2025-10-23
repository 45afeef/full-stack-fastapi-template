import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate
from app.models.travel.cab import Cab, Driver
from app.models.travel.providers import (
    ServiceProvider,
    StayServiceProvider,
    StayServiceProvider as StayProviderModel,
)
from app.models.travel.stay import StayUnit, StayAmenity
from app.models.travel.providers import TravelAgency, TravelAgencyStaff
from sqlalchemy import func
from sqlmodel import select
from typing import List


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item():
    raise NotImplementedError("Item model removed — this function has been deprecated")


def create_service_provider(*, session: Session, provider: dict | ServiceProvider) -> ServiceProvider:
    # Accept dicts (from DTOs) or ServiceProvider instances
    if isinstance(provider, dict):
        obj = ServiceProvider(**provider)
    else:
        obj = provider
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def create_stay_provider_row(*, session: Session, provider_id) -> StayServiceProvider:
    obj = StayServiceProvider(provider_id=provider_id)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def create_stay_unit(*, session: Session, unit: dict | StayUnit) -> StayUnit:
    if isinstance(unit, dict):
        obj = StayUnit(**unit)
    else:
        obj = unit
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def create_travel_agency(*, session: Session, agency: dict | TravelAgency) -> TravelAgency:
    if isinstance(agency, dict):
        obj = TravelAgency(**agency)
    else:
        obj = agency
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def assign_agency_staff(*, session: Session, staff: dict | TravelAgencyStaff) -> TravelAgencyStaff:
    if isinstance(staff, dict):
        obj = TravelAgencyStaff(**staff)
    else:
        obj = staff
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def get_travel_agency(*, session: Session, agency_id: str) -> TravelAgency | None:
    return session.get(TravelAgency, agency_id)


def list_travel_agencies(*, session: Session, limit: int = 100, offset: int = 0) -> list[TravelAgency]:
    statement = select(TravelAgency).offset(offset).limit(limit)
    return session.exec(statement).all()


def update_travel_agency(*, session: Session, db_agency: TravelAgency, agency_in: dict) -> TravelAgency:
    db_agency.sqlmodel_update(agency_in, update={})
    session.add(db_agency)
    session.commit()
    session.refresh(db_agency)
    return db_agency


def delete_travel_agency(*, session: Session, db_agency: TravelAgency) -> None:
    session.delete(db_agency)
    session.commit()


def get_agency_staff(*, session: Session, staff_id: str) -> TravelAgencyStaff | None:
    return session.get(TravelAgencyStaff, staff_id)


def update_agency_staff(*, session: Session, db_staff: TravelAgencyStaff, staff_in: dict) -> TravelAgencyStaff:
    db_staff.sqlmodel_update(staff_in, update={})
    session.add(db_staff)
    session.commit()
    session.refresh(db_staff)
    return db_staff


def remove_agency_staff(*, session: Session, db_staff: TravelAgencyStaff) -> None:
    session.delete(db_staff)
    session.commit()


def list_stay_units(
    *,
    session: Session,
    provider_id: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    amenity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[StayUnit], int]:
    statement = select(StayUnit)
    if provider_id:
        statement = statement.where(StayUnit.provider_id == provider_id)
    if min_price is not None:
        statement = statement.where(StayUnit.room_rate >= min_price)
    if max_price is not None:
        statement = statement.where(StayUnit.room_rate <= max_price)
    # amenity filtering requires join with StayAmenity
    if amenity:
        from sqlmodel import select as _select

        statement = (
            _select(StayUnit)
            .join(StayAmenity, StayAmenity.stay_unit_id == StayUnit.id)
            .where(StayAmenity.amenity == amenity)
        )

    # compute total count approximately (avoids complex subquery issues)
    total = None
    # fallback without accurate count to keep it simple
    results = session.exec(statement.offset(offset).limit(limit)).all()
    count = len(results) if total is None else total
    return results, count


def delete_service_provider(*, session: Session, db_provider: ServiceProvider) -> None:
    # remove related stay units and amenities
    try:
        statement = select(StayUnit).where(StayUnit.provider_id == db_provider.id)
        units = session.exec(statement).all()
        for u in units:
            # delete amenities linked to unit
            statement_a = select(StayAmenity).where(StayAmenity.stay_unit_id == u.id)
            amenities = session.exec(statement_a).all()
            for a in amenities:
                session.delete(a)
            session.delete(u)

        # remove cab and driver rows
        try:
            from app.models.travel.cab import Cab, Driver

            statement_c = select(Cab).where(Cab.provider_id == db_provider.id)
            cabs = session.exec(statement_c).all()
            for c in cabs:
                session.delete(c)
            statement_d = select(Driver).where(Driver.provider_id == db_provider.id)
            drivers = session.exec(statement_d).all()
            for d in drivers:
                session.delete(d)
        except Exception:
            # cab models may not be present in some states; ignore if not available
            pass

        # remove provider-specific rows
        try:
            from app.models.travel.providers import StayServiceProvider, CabServiceProvider

            ssp = session.get(StayServiceProvider, db_provider.id)
            if ssp:
                session.delete(ssp)
            csp = session.get(CabServiceProvider, db_provider.id)
            if csp:
                session.delete(csp)
        except Exception:
            pass

        session.delete(db_provider)
        session.commit()
    except Exception:
        session.rollback()
        raise


def create_cab(*, session: Session, cab: dict | Cab) -> Cab:
    if isinstance(cab, dict):
        obj = Cab(**cab)
    else:
        obj = cab
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def list_cabs(*, session: Session, provider_id: str, limit: int = 100, offset: int = 0):
    statement = select(Cab).where(Cab.provider_id == provider_id).offset(offset).limit(limit)
    return session.exec(statement).all()


def create_driver(*, session: Session, driver: dict | Driver) -> Driver:
    if isinstance(driver, dict):
        obj = Driver(**driver)
    else:
        obj = driver
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def list_drivers(*, session: Session, provider_id: str, limit: int = 100, offset: int = 0):
    statement = select(Driver).where(Driver.provider_id == provider_id).offset(offset).limit(limit)
    return session.exec(statement).all()
