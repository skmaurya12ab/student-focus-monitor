from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.account import router as account_router
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(sessions_router)
api_router.include_router(websocket_router)

__all__ = ["api_router"]
