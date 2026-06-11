from fastapi import APIRouter

from app.api.routes import auth, charts, health, portfolio

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(portfolio.router)
api_router.include_router(charts.router)
