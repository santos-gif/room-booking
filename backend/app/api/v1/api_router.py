from fastapi import APIRouter

from backend.app.api.v1.booking_router import router as booking_router


api_router = APIRouter()

api_router.include_router(booking_router)
