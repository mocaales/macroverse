from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from google.cloud.firestore_v1 import Client
from pydantic import BaseModel, EmailStr

from app.core.firebase import get_firebase_app, get_firestore_client
from app.core.market_database import get_market_pool
from app.repositories.market import MarketRepository
from app.repositories.portfolio import PortfolioRepository

bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    uid: str
    email: EmailStr


def get_db() -> Client:
    return get_firestore_client()


def get_portfolio_repository(db: Annotated[Client, Depends(get_db)]) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_market_repository() -> MarketRepository | None:
    pool = get_market_pool()
    return MarketRepository(pool) if pool else None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        token = auth.verify_id_token(credentials.credentials, app=get_firebase_app())
    except (ValueError, FirebaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is invalid or expired.",
        ) from exc
    email = token.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An email address is required.")
    return AuthenticatedUser(uid=token["uid"], email=email)
