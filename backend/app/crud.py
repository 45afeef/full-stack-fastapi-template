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


def list_cabs_query(
    *,
    session: Session,
    provider_id: str | None = None,
    provider_ids: list[str] | None = None,
    vehicle_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """More flexible cab listing used by query endpoints.

    - provider_id: single provider id
    - provider_ids: list of provider ids to include
    - vehicle_type: filter by vehicle_type (string)
    """
    statement = select(Cab)
    if provider_id:
        statement = statement.where(Cab.provider_id == provider_id)
    if provider_ids:
        statement = statement.where(Cab.provider_id.in_(provider_ids))
    if vehicle_type:
        statement = statement.where(Cab.vehicle_type == vehicle_type)
    results = session.exec(statement.offset(offset).limit(limit)).all()
    # count is approximate here
    return results, len(results)


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


def list_drivers_query(
    *,
    session: Session,
    provider_id: str | None = None,
    provider_ids: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Flexible driver listing used by query endpoints."""
    statement = select(Driver)
    if provider_id:
        statement = statement.where(Driver.provider_id == provider_id)
    if provider_ids:
        statement = statement.where(Driver.provider_id.in_(provider_ids))
    results = session.exec(statement.offset(offset).limit(limit)).all()
    return results, len(results)


def _providers_within_bbox(session: Session, lat: float, lon: float, radius_km: float) -> list[str]:
    """Return provider ids whose location falls within a simple bounding box around (lat, lon).

    This is a fast pre-filter; callers can compute exact haversine distance later if needed.
    """
    # approximate degrees per km
    import math

    delta_lat = radius_km / 111.0
    if abs(lat) >= 90:
        delta_lon = 180.0
    else:
        delta_lon = radius_km / (111.320 * max(0.000001, math.cos(math.radians(lat))))

    from app.models.travel.providers import ServiceProvider
    from app.models.travel.location import Location
    from sqlmodel import select as _select

    stmt = (
        _select(ServiceProvider.id)
        .join(Location, ServiceProvider.location_id == Location.id)
        .where(Location.latitude >= (lat - delta_lat))
        .where(Location.latitude <= (lat + delta_lat))
        .where(Location.longitude >= (lon - delta_lon))
        .where(Location.longitude <= (lon + delta_lon))
    )
    rows = session.exec(stmt).all()
    # rows may be list of ids or list of tuples depending on SQL backend; normalize
    provider_ids = [str(r[0]) if isinstance(r, tuple) else str(r) for r in rows]
    return provider_ids


def list_stay_units_by_location(
    *,
    session: Session,
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    amenity: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    limit: int = 100,
    offset: int = 0,
    sort_by_distance: bool = False,
):
    """Find stay units near a lat/lon within radius_km.

    This performs a bbox prefilter using provider location, then fetches stay units for matching providers.
    If sort_by_distance is True the results are sorted by haversine distance (computed in Python).
    Returns (units, count).
    """
    import math

    # get candidate provider ids using bbox
    provider_ids = _providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    # no providers nearby
    if not provider_ids:
        return [], 0

    # reuse existing list_stay_units functionality but need to filter by provider_ids
    from sqlmodel import select as _select
    from app.models.travel.stay import StayUnit, StayAmenity
    from app.models.travel.providers import ServiceProvider
    from app.models.travel.location import Location

    stmt = _select(StayUnit).where(StayUnit.provider_id.in_(provider_ids))
    if min_price is not None:
        stmt = stmt.where(StayUnit.room_rate >= min_price)
    if max_price is not None:
        stmt = stmt.where(StayUnit.room_rate <= max_price)
    if amenity:
        stmt = (
            _select(StayUnit)
            .join(StayAmenity, StayAmenity.stay_unit_id == StayUnit.id)
            .where(StayAmenity.amenity == amenity)
            .where(StayUnit.provider_id.in_(provider_ids))
        )

    results = session.exec(stmt).all()

    # if sorting by distance is requested, compute distance per result using provider's location
    if sort_by_distance and results:
        # build map of provider_id -> (lat, lon)
        stmt_loc = _select(ServiceProvider.id, Location.latitude, Location.longitude).join(Location, ServiceProvider.location_id == Location.id).where(ServiceProvider.id.in_(provider_ids))
        loc_rows = session.exec(stmt_loc).all()
        provider_loc = {}
        for row in loc_rows:
            # row may be tuple (id, lat, lon)
            pid = str(row[0]) if isinstance(row, tuple) else str(row.id)
            if isinstance(row, tuple):
                provider_loc[pid] = (float(row[1]), float(row[2]))
            else:
                provider_loc[pid] = (float(row.latitude), float(row.longitude))

        def haversine_km(a_lat, a_lon, b_lat, b_lon):
            R = 6371.0
            phi1 = math.radians(a_lat)
            phi2 = math.radians(b_lat)
            dphi = math.radians(b_lat - a_lat)
            dlambda = math.radians(b_lon - a_lon)
            aa = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
            return 2 * R * math.asin(math.sqrt(aa))

        units_with_dist = []
        for u in results:
            pid = str(u.provider_id)
            if pid in provider_loc:
                plat, plon = provider_loc[pid]
                d = haversine_km(lat, lon, plat, plon)
            else:
                d = float("inf")
            units_with_dist.append((u, d))

        units_with_dist.sort(key=lambda x: x[1])
        sorted_units = [u for u, _ in units_with_dist]
    else:
        sorted_units = results

    # slice for pagination
    paged = sorted_units[offset : offset + limit]
    return paged, len(sorted_units)
