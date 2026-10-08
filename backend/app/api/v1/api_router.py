from fastapi import APIRouter

from app.api.v1.appointment.router import router as appointment_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.google_auth.router import router as google_auth_router
api_router = APIRouter(prefix="/api/v1")

api_router.include_router(appointment_router)
api_router.include_router(auth_router)
api_router.include_router(google_auth_router)
