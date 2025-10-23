import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import SessionDep, CurrentUser, get_current_active_superuser, get_current_user
from app import crud
from app.models import User
from app.models.travel.providers import ServiceProvider, CabServiceProvider
from app.models.travel.cab import Cab, Driver
from app.schemas.provider.cab import CabCreate, CabPublic, DriverCreate, DriverPublic

router = APIRouter(prefix="/{provider_id}/cab", tags=["providers-cab"])


def _is_provider_owner(session: SessionDep, user: User, provider: ServiceProvider) -> bool:
    return provider.owner_id == user.id


@router.post(
    "", 
    response_model=CabPublic, 
    dependencies=[Depends(get_current_active_superuser)],
)
def create_cab(*, provider_id: uuid.UUID, session: SessionDep, cab: CabCreate) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    # ensure provider is a cab provider
    sp = session.get(CabServiceProvider, provider_id)
    if not sp:
        raise HTTPException(status_code=400, detail="Provider is not a cab provider")
    # create cab
    cab_obj = Cab(**cab.model_dump(), provider_id=provider_id)
    created = crud.create_cab(session=session, cab=cab_obj)
    return created


@router.get(
    "",
    response_model=list[CabPublic],
)
def list_cabs(*, provider_id: uuid.UUID, session: SessionDep, current_user: CurrentUser, limit: int = Query(default=100), offset: int = Query(default=0)) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    # only superuser or agency staff can query; owner can query
    if not (current_user.is_superuser or _is_provider_owner(session, current_user, provider)):
        raise HTTPException(status_code=403, detail="Not authorized to list cabs")
    return crud.list_cabs(session=session, provider_id=str(provider_id), limit=limit, offset=offset)


@router.post(
    "/drivers", 
    response_model=DriverPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_driver(*, provider_id: uuid.UUID, session: SessionDep, driver: DriverCreate) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    driver_obj = Driver(**driver.model_dump(), provider_id=provider_id)
    created = crud.create_driver(session=session, driver=driver_obj)
    return created

@router.get(
    "/drivers",
    response_model=list[DriverPublic],
)
def list_drivers(*, provider_id: uuid.UUID, session: SessionDep, current_user: CurrentUser, limit: int = Query(default=100), offset: int = Query(default=0)) -> Any:
    provider = session.get(ServiceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not (current_user.is_superuser or _is_provider_owner(session, current_user, provider)):
        raise HTTPException(status_code=403, detail="Not authorized to list drivers")
    return crud.list_drivers(session=session, provider_id=str(provider_id), limit=limit, offset=offset)


__all__ = ["router"]
