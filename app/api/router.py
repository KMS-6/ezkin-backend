from fastapi import APIRouter

from app.modules.care.router import router as care_router
from app.modules.quick_care.router import router as quick_care_router
from app.modules.shelf.router import router as shelf_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(shelf_router)
api_router.include_router(care_router)
api_router.include_router(quick_care_router)
