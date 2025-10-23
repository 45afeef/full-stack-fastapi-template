import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import SessionDep, CurrentUser, get_current_active_superuser
from app import crud
from app.models import User
from app.models.travel.providers import ServiceProvider
from app.schemas.provider import ProviderCreate, ProviderPublic

router = APIRouter()


def _is_provider_owner(session: Session, user: User, provider: ServiceProvider) -> bool:
    return provider.owner_id == user.id


@router.post("/", response_model=ProviderPublic, dependencies=[Depends(get_current_active_superuser)],)
def create_provider(*, session: SessionDep, provider: ProviderCreate) -> Any:
    """Superuser: create a service provider."""
    # validate created_by user
    user = session.get(User, provider.created_by)
    if not user:
        raise HTTPException(status_code=404, detail="User not found for created_by")
    sp = ServiceProvider(**provider.model_dump())
    created = crud.create_service_provider(session=session, provider=sp)
    return created


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
