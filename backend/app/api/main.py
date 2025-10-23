from fastapi import APIRouter

from app.api.routes import login, private, users, utils, stays, agency
from app.api.routes import providers
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(agency.router)
api_router.include_router(stays.router)
api_router.include_router(utils.router)
api_router.include_router(providers.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
