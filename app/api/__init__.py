from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.routes import router as app_router

router = APIRouter()
router.include_router(app_router)
router.include_router(admin_router)

__all__ = ["router"]
