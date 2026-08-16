from fastapi import APIRouter

from app.modules.briefings.router import router as briefings_router
from app.modules.care.router import router as care_router
from app.modules.cosmetics_catalog.router import router as cosmetics_catalog_router
from app.modules.feedback.router import router as feedback_router
from app.modules.health_metrics.router import router as health_metrics_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.onboarding.router import router as onboarding_router
from app.modules.personas.router import router as personas_router
from app.modules.quick_care.router import router as quick_care_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.risk.router import router as risk_router
from app.modules.shelf.router import router as shelf_router
from app.modules.skin_scans.router import router as skin_scans_router
from app.modules.triggers.router import router as triggers_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(shelf_router)
api_router.include_router(care_router)
api_router.include_router(quick_care_router)
api_router.include_router(personas_router)
api_router.include_router(onboarding_router)
api_router.include_router(skin_scans_router)
api_router.include_router(health_metrics_router)
api_router.include_router(risk_router)
api_router.include_router(briefings_router)
api_router.include_router(cosmetics_catalog_router)
api_router.include_router(triggers_router)
api_router.include_router(recommendations_router)
api_router.include_router(knowledge_router)
api_router.include_router(feedback_router)
