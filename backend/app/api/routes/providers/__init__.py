from fastapi import APIRouter

from app.api.routes.providers import provider, cab, stay

router = APIRouter(prefix="/providers", tags=["providers"]) 

router.include_router(provider.router)
router.include_router(cab.router)
router.include_router(stay.router)

__all__ = ["router"]
