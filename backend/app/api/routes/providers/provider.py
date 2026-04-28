import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import SessionDep, CurrentUser, get_current_active_superuser
from app import crud
from app.models import User
from app.models.travel.providers import ServiceProvider
from app.schemas.provider import ProviderCreate, ProviderPublic
from app.models.travel.providers import CabServiceProvider, StayServiceProvider

router = APIRouter(tags=["providers"]) 


def _is_provider_owner(session: Session, user: User, provider: ServiceProvider) -> bool:
    return provider.owner_id == user.id


@router.post(
    "/", 
    response_model=ProviderPublic,
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def create_provider(*, session: SessionDep, provider_in: ProviderCreate) -> Any:
    """Superuser: create a service provider.
    
    Service provider can be any of the follwoing two
    1. Cab Service Provider
    2. Stay Service Provider
    
    Requires latitude and longitude to create a location.
    """
    # validate users
    create_by_user = session.get(User, provider_in.created_by)
    if not create_by_user:
        raise HTTPException(status_code=404, detail="User not found for created_by")
    owner_user = session.get(User, provider_in.owner_id)
    if not owner_user:
        raise HTTPException(status_code=404, detail="User not found for owner_id")
    
    # Create location with latitude and longitude
    location = crud.create_location(
        session=session,
        latitude=provider_in.latitude,
        longitude=provider_in.longitude,
    )
    
    # Prepare provider data with location_id
    provider_data = provider_in.model_dump()
    provider_data["location_id"] = location.id
    # Remove latitude and longitude from provider_data as they're not provider fields
    provider_data.pop("latitude", None)
    provider_data.pop("longitude", None)
    
    # Create the service provider
    sp = ServiceProvider(**provider_data)
    provider = crud.create_service_provider(session=session, provider=sp)
    
    if provider_in.provider_type == "CAB":
        cab = CabServiceProvider(provider_id=provider.id)
        session.add(cab)

    elif provider_in.provider_type == "STAY":
        stay = StayServiceProvider(
            provider_id=provider.id,
            property_type=provider_in.property_type,
            room_count=provider_in.room_count,
            optimal_occupancy=provider_in.optimal_occupancy,
            max_occupancy=provider_in.max_occupancy,
        )
        session.add(stay)

    session.commit()
    session.refresh(provider)
    return provider


@router.get("/", response_model=list[ProviderPublic])
def list_providers(*, session: SessionDep, current_user: CurrentUser) -> Any:
    """List providers: superusers see all, agency staff may query; regular users only their owned providers."""
    # simple listing for now: return all to superuser, else filter by owner
    if current_user.is_superuser:
        statement = select(ServiceProvider)
        return session.exec(statement).all()
    # otherwise only providers owned by user
    statement = select(ServiceProvider).where(ServiceProvider.owner_id == current_user.id)
    return session.exec(statement).all()


@router.get("/{provider_id}", response_model=ProviderPublic)
def get_provider(*, provider_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> Any:
    db = session.get(ServiceProvider, provider_id)
    if not db:
        raise HTTPException(status_code=404, detail="Provider not found")
    if current_user.is_superuser or _is_provider_owner(session, current_user, db):
        return db
    # provider staff or agency staff checks may be added later
    raise HTTPException(status_code=403, detail="Not authorized to view provider")


@router.patch("/{provider_id}", response_model=ProviderPublic)
def update_provider(*, provider_id: uuid.UUID, session: SessionDep, provider_in: ProviderCreate, current_user: CurrentUser) -> Any:
    db = session.get(ServiceProvider, provider_id)
    if not db:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not (current_user.is_superuser or _is_provider_owner(session, current_user, db)):
        raise HTTPException(status_code=403, detail="Not authorized to update provider")
    db.sqlmodel_update(provider_in.model_dump(exclude_unset=True), update={})
    session.add(db)
    session.commit()
    session.refresh(db)
    return db


@router.delete("/{provider_id}", dependencies=[Depends(get_current_active_superuser)],)
def delete_provider(*, provider_id: uuid.UUID, session: SessionDep) -> Any:
    db = session.get(ServiceProvider, provider_id)
    if not db:
        raise HTTPException(status_code=404, detail="Provider not found")
    crud.delete_service_provider(session=session, db_provider=db)
    return {"ok": True}


__all__ = ["router"]
