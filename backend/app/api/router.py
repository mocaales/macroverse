from fastapi import APIRouter

from app.api.routes import admin, auth, charts, health, portfolio

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(portfolio.router)
api_router.include_router(charts.router)
