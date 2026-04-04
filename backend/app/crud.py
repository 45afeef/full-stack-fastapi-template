import uuid
from typing import Any,List

from sqlmodel import Session, select, distinct, or_

from app.core.security import get_password_hash, verify_password
from app.models import User, UserCreate, UserUpdate
from app.models.travel.cab import Cab, Driver
from app.models.travel.providers import (
    CabServiceProvider,
    ServiceProvider,
    StayServiceProvider,
    StayServiceProvider as StayProviderModel,
)
from app.models.travel.stay import StayUnit, StayAmenity
from app.models.travel.providers import TravelAgency, TravelAgencyStaff
from sqlalchemy import func



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


def get_user_by_phone(*, session: Session, phone_number: str) -> User | None:
    statement = select(User).where(User.phone_number == phone_number)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, phone_number: str, password: str) -> User | None:
    db_user = get_user_by_phone(session=session, phone_number=phone_number)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


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


def create_cab_provider_row(*, session: Session, provider_id: str) -> CabServiceProvider:
    obj = CabServiceProvider(provider_id=provider_id)
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


def create_stay_amenity(*, session: Session, amenity: dict | StayAmenity) -> StayAmenity:
    if isinstance(amenity, dict):
        obj = StayAmenity(**amenity)
    else:
        obj = amenity
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def list_stay_amenities(
    *,
    session: Session,
    provider_id: str,
    unit_id: str,
) -> list[StayAmenity]:
    statement = (
        select(StayAmenity)
        .where(StayAmenity.stay_service_provider_id == provider_id)
        .where(StayAmenity.stay_unit_id == unit_id)
    )
    return session.exec(statement).all()


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


def list_stay_providers(
    *,
    session: Session,
    location_id: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    pax_count: int | None = None,
    amenities: List[str] | None = None,
    min_rating: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[ServiceProvider], int]:
    """
    List stay providers with flexible filtering and pagination.
    
    **Filters** (all optional, combined with AND logic):
    - `location_id`: Filter by provider location ID
    - `min_price` / `max_price`: Filter by unit room_rate (inclusive)
    - `pax_count`: Filter providers with units having sufficient capacity
    - `amenities`: AND semantics. Providers must have units with ALL listed amenities
    - `min_rating`: Filter by minimum average rating (reserved for future use)
    
    **Pagination**: 
    - Results offset by `offset` items
    - Limited to `limit` items per page
    
    **Return**: Tuple of (results: List[ServiceProvider], count: int)
    """
    # Start from stay-specific provider rows and join the base provider metadata.
    statement = (
        select(ServiceProvider)
        .join(StayServiceProvider, StayServiceProvider.provider_id == ServiceProvider.id)
        .where(ServiceProvider.provider_type == "STAY")
    )
    
    # Filter by location if specified
    if location_id:
        statement = statement.where(ServiceProvider.location_id == location_id)
    
    # Filter by stay-provider level occupancy if specified
    if pax_count:
        statement = statement.where(StayServiceProvider.max_occupancy >= pax_count)

    # Check if we have any unit-based filters (price, pax, amenities)
    has_unit_filters = min_price is not None or max_price is not None or amenities
    
    if has_unit_filters:
        statement = statement.join(StayUnit, StayUnit.provider_id == ServiceProvider.id)
        
        # Filter by price range
        if min_price is not None:
            statement = statement.where(StayUnit.room_rate >= min_price)
        if max_price is not None:
            statement = statement.where(StayUnit.room_rate <= max_price)
        
        # Filter by amenities using AND semantics: provider must have ALL listed amenities
        if amenities:
            # Subquery: find provider IDs that have units with all requested amenities
            # Group by provider and count distinct amenities; keep only providers with all amenities
            subq = (
                select(StayAmenity.stay_service_provider_id)
                .where(StayAmenity.amenity.in_(amenities))
                .group_by(StayAmenity.stay_service_provider_id)
                .having(func.count(distinct(StayAmenity.amenity)) >= len(amenities))
            )
            
            # Filter providers to those in the subquery
            statement = statement.where(ServiceProvider.id.in_(subq))
        
        # Apply distinct to avoid duplicates from joins
        statement = statement.distinct()
    
    # Apply pagination
    results = session.exec(statement.offset(offset).limit(limit)).all()
    count = len(results)
    
    return results, count


def list_stay_units(
    *,
    session: Session,
    provider_id: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    pax_count: int | None = None,
    amenities: List[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[StayUnit], int]:
    """
    List stay units with flexible filtering and pagination.
    
    **Filters** (all optional, combined with AND logic):
    - `provider_id`: Restrict to specific provider's units
    - `min_price` / `max_price`: Filter by room_rate (inclusive)
    - `pax_count`: Filter by occupancy. A unit matches if EITHER:
      - Its max_occupancy >= pax_count (single unit has capacity)
      - OR the provider's total capacity (sum of all units' max_occupancy) >= pax_count
      - Uses subquery to check provider total capacity
    - `amenities`: AND semantics. Unit must have ALL listed amenities.
      - Uses subquery: select unit IDs with amenities, group by unit, count distinct amenities, 
      - then filter to units where count(distinct amenities) >= len(amenities_list)
    
    **Pagination**: 
    - Results offset by `offset` items
    - Limited to `limit` items per page
    
    **Return**: Tuple of (results: List[StayUnit], count: int)
    - count = len(results) if no total precomputed (current behavior)
    - Note: Count is approximate due to pagination not computing full result set
    """
    statement = select(StayUnit)
    
    # Filter by provider if specified
    if provider_id:
        statement = statement.where(StayUnit.provider_id == provider_id)
    
    # Filter by price range
    if min_price is not None:
        statement = statement.where(StayUnit.room_rate >= min_price)
    if max_price is not None:
        statement = statement.where(StayUnit.room_rate <= max_price)

    # Filter by occupancy: unit itself or provider's total capacity must meet pax_count
    if pax_count:
        # Subquery: sum of max_occupancy per provider
        provider_capacity_subq = (
            select(
                StayUnit.provider_id,
                func.sum(StayUnit.max_occupancy).label("total_capacity")
            )
            .group_by(StayUnit.provider_id)
            .subquery()
        )
        
        # Join and filter: unit has capacity OR provider has total capacity
        statement = statement.join(
            provider_capacity_subq,
            StayUnit.provider_id == provider_capacity_subq.c.provider_id
        ).where(
            or_(
                StayUnit.max_occupancy >= pax_count,
                provider_capacity_subq.c.total_capacity >= pax_count
            )
        )
    
    # Filter by amenities using AND semantics: unit must have ALL listed amenities
    if amenities:
        # Subquery: find unit IDs that have all requested amenities
        # Group by unit_id and count distinct amenities; keep only units with all amenities
        subq = (
            select(StayAmenity.stay_unit_id)
            .where(StayAmenity.amenity.in_(amenities))
            .group_by(StayAmenity.stay_unit_id)
            .having(func.count(distinct(StayAmenity.amenity)) >= len(amenities))
        )
        
        # Join units to the subquery
        statement = statement.where(StayUnit.id.in_(subq))

    # Compute total count (approximate: only counts what's returned on this page)
    # TODO: For accurate total count across pagination, consider SELECT COUNT(*) before offset/limit
    results = session.exec(statement.offset(offset).limit(limit)).all()
    count = len(results)  # Approximate count based on this page's results
    
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
) -> tuple[List[Cab], int]:
    """
    Flexible cab listing used by query endpoints. Supports single provider, multiple providers, or vehicle type filtering.
    
    **Filters** (all optional, combined with AND logic):
    - `provider_id`: Single provider. If specified, only cabs from this provider are returned.
    - `provider_ids`: List of provider IDs. If specified, cabs from any of these providers are included.
      - Note: If both provider_id and provider_ids are specified, provider_id takes precedence.
    - `vehicle_type`: Filter cabs by vehicle type (e.g., SEDAN, SUV, HATCHBACK).
    
    **Pagination**: 
    - Results are offset by `offset` items
    - Limited to `limit` items per page
    
    **Return**: Tuple of (results: List[Cab], count: int)
    - count = len(results) (approximate, only this page)
    """
    statement = select(Cab)
    
    # Filter by single provider if specified
    if provider_id:
        statement = statement.where(Cab.provider_id == provider_id)
    
    # Filter by multiple provider IDs if specified
    if provider_ids:
        statement = statement.where(Cab.provider_id.in_(provider_ids))
    
    # Filter by vehicle type
    if vehicle_type:
        statement = statement.where(Cab.vehicle_type == vehicle_type)
    
    # Execute with pagination
    results = session.exec(statement.offset(offset).limit(limit)).all()
    count = len(results)  # Approximate count based on this page
    
    return results, count


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
) -> tuple[List[Driver], int]:
    """
    Flexible driver listing used by query endpoints. Supports single provider or multiple provider filtering.
    
    **Filters** (all optional, combined with AND logic):
    - `provider_id`: Single provider. If specified, only drivers from this provider are returned.
    - `provider_ids`: List of provider IDs. If specified, drivers from any of these providers are included.
      - Note: If both provider_id and provider_ids are specified, provider_id takes precedence.
    
    **Pagination**: 
    - Results are offset by `offset` items
    - Limited to `limit` items per page
    
    **Return**: Tuple of (results: List[Driver], count: int)
    - count = len(results) (approximate, only this page)
    """
    statement = select(Driver)
    
    # Filter by single provider if specified
    if provider_id:
        statement = statement.where(Driver.provider_id == provider_id)
    
    # Filter by multiple provider IDs if specified
    if provider_ids:
        statement = statement.where(Driver.provider_id.in_(provider_ids))
    
    # Execute with pagination
    results = session.exec(statement.offset(offset).limit(limit)).all()
    
    return results, len(results)


def _providers_within_bbox(session: Session, lat: float, lon: float, radius_km: float) -> list[str]:
    """
    Return provider IDs whose location falls within a bounding box around (lat, lon).

    **Algorithm**:
    - Uses simple lat/lon bounding box (fast, no trigonometry overhead)
    - NOT exact haversine distance; approximate tolerance of ±0.1° per 11km
    - Suitable for pre-filtering; callers can compute exact distances if needed
    
    **Coordinate Conversion**:
    - 1 degree of latitude ≈ 111 km (constant)
    - 1 degree of longitude varies by latitude: 111 * cos(latitude) km
      - At equator (0°): 111 km
      - At 45°: ~78 km
      - At poles: ~0 km
    
    **Edge Cases**:
    - If lat >= 90 or lat <= -90: delta_lon set to 180° (covers all longitudes, as we're at pole)
    
    **Returns**: List of provider UUIDs (as strings) that fall within the bounding box.
    """
    import math

    # Compute delta_lat: how many degrees equal radius_km in the north-south direction
    delta_lat = radius_km / 111.0
    
    # Compute delta_lon: accounts for the fact that longitude lines converge at the poles
    if abs(lat) >= 90:
        # At the poles, all longitudes are adjacent; cover all
        delta_lon = 180.0
    else:
        # At other latitudes, use cos(lat) to adjust for longitude convergence
        delta_lon = radius_km / (111.320 * max(0.000001, math.cos(math.radians(lat))))

    from app.models.travel.providers import ServiceProvider
    from app.models.travel.location import Location
    from sqlmodel import select as _select

    # Query providers with location within the bounding box
    stmt = (
        _select(ServiceProvider.id)
        .join(Location, ServiceProvider.location_id == Location.id)
        .where(Location.latitude >= (lat - delta_lat))
        .where(Location.latitude <= (lat + delta_lat))
        .where(Location.longitude >= (lon - delta_lon))
        .where(Location.longitude <= (lon + delta_lon))
    )
    
    rows = session.exec(stmt).all()
    
    # Normalize output: rows may be list of IDs or list of tuples depending on SQL backend
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
) -> tuple[List[StayUnit], int]:
    """
    Find stay units near a geographic point with optional filters and distance-based sorting.
    
    **Algorithm Overview**:
    1. Use _providers_within_bbox() to pre-filter providers by location (fast bounding box)
    2. Fetch all stay units from those providers with filters applied
    3. Optionally sort by haversine distance using provider location
    4. Apply pagination (offset/limit)
    
    **Filters** (all optional, combined with AND logic):
    - `amenity`: Single amenity filter (e.g., "wifi"). Unlike /query/units, this is NOT AND semantics.
    - `min_price` / `max_price`: Filter by room_rate (inclusive bounds).
    
    **Distance Sorting**:
    - If `sort_by_distance=True`:
      - Computes haversine distance from (lat, lon) to each provider's location
      - Results sorted by distance (nearest first)
      - Distance calculation in Python (not SQL) for accuracy
    - If `sort_by_distance=False`:
      - Results returned in database order (typically creation order)
    
    **Pagination**:
    - Applied AFTER sorting
    - Slices sorted_units[offset : offset + limit]
    
    **Return**: 
    - Tuple of (results: List[StayUnit], count: int)
    - count = total number of matching units (before pagination), NOT page size
    
    **Performance Notes**:
    - Bounding box is approximate but fast
    - Full haversine distance computed only if sort_by_distance=True
    - Suitable for real-time APIs with 1000s of units
    """
    import math

    # Step 1: Pre-filter providers using bounding box (fast)
    provider_ids = _providers_within_bbox(session=session, lat=lat, lon=lon, radius_km=radius_km)

    # No providers nearby; return empty results
    if not provider_ids:
        return [], 0

    # Step 2: Fetch stay units from nearby providers with filters
    from sqlmodel import select as _select
    from app.models.travel.stay import StayUnit, StayAmenity
    from app.models.travel.providers import ServiceProvider
    from app.models.travel.location import Location

    # Base query: units from nearby providers
    stmt = _select(StayUnit).where(StayUnit.provider_id.in_(provider_ids))
    
    # Apply price filters
    if min_price is not None:
        stmt = stmt.where(StayUnit.room_rate >= min_price)
    if max_price is not None:
        stmt = stmt.where(StayUnit.room_rate <= max_price)
    
    # Apply amenity filter (single amenity, not AND semantics like /query/units)
    if amenity:
        stmt = (
            _select(StayUnit)
            .join(StayAmenity, StayAmenity.stay_unit_id == StayUnit.id)
            .where(StayAmenity.amenity == amenity)
            .where(StayUnit.provider_id.in_(provider_ids))
        )

    # Execute query to get all matching results (before pagination)
    results = session.exec(stmt).all()

    # Step 3: Optionally sort by haversine distance
    if sort_by_distance and results:
        # Fetch provider locations for distance calculation
        stmt_loc = (
            _select(ServiceProvider.id, Location.latitude, Location.longitude)
            .join(Location, ServiceProvider.location_id == Location.id)
            .where(ServiceProvider.id.in_(provider_ids))
        )
        loc_rows = session.exec(stmt_loc).all()
        
        # Build provider_id -> (lat, lon) map
        provider_loc = {}
        for row in loc_rows:
            # Handle both tuple and object returns
            pid = str(row[0]) if isinstance(row, tuple) else str(row.id)
            if isinstance(row, tuple):
                provider_loc[pid] = (float(row[1]), float(row[2]))
            else:
                provider_loc[pid] = (float(row.latitude), float(row.longitude))

        def haversine_km(a_lat, a_lon, b_lat, b_lon):
            """Compute great-circle distance in kilometers using haversine formula."""
            R = 6371.0  # Earth's radius in km
            phi1 = math.radians(a_lat)
            phi2 = math.radians(b_lat)
            dphi = math.radians(b_lat - a_lat)
            dlambda = math.radians(b_lon - a_lon)
            aa = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
            return 2 * R * math.asin(math.sqrt(aa))

        # Compute distance for each unit based on its provider's location
        units_with_dist = []
        for u in results:
            pid = str(u.provider_id)
            if pid in provider_loc:
                plat, plon = provider_loc[pid]
                d = haversine_km(lat, lon, plat, plon)
            else:
                # Provider location missing; assign infinite distance (should not happen)
                d = float("inf")
            units_with_dist.append((u, d))

        # Sort by distance (nearest first)
        units_with_dist.sort(key=lambda x: x[1])
        sorted_units = [u for u, _ in units_with_dist]
    else:
        # No sorting; use database order
        sorted_units = results

    # Step 4: Apply pagination
    paged = sorted_units[offset : offset + limit]
    total_count = len(sorted_units)  # Total matching units
    
    return paged, total_count

