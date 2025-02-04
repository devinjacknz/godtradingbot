"""API Gateway routes package."""

from fastapi import APIRouter

from .auth import router as auth_router

router = APIRouter()

# Include auth routes
router.include_router(auth_router, prefix="/auth", tags=["auth"])
