from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from google.cloud.firestore_v1 import Client
from pydantic import BaseModel, EmailStr

from app.core.config import get_settings
from app.core.firebase import get_firebase_app, get_firestore_client
from app.core.market_database import get_market_pool
from app.models.auth import UserRole
from app.repositories.market import MarketRepository
from app.repositories.portfolio import PortfolioRepository

bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    uid: str
    email: EmailStr
    role: UserRole = "user"
    email_verified: bool = False


def get_db() -> Client:
    return get_firestore_client()


def get_portfolio_repository(db: Annotated[Client, Depends(get_db)]) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_market_repository() -> MarketRepository | None:
    pool = get_market_pool()
    return MarketRepository(pool, batch_size=get_settings().market_database_batch_size) if pool else None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        token = auth.verify_id_token(
            credentials.credentials,
            app=get_firebase_app(),
            check_revoked=True,
        )
    except (ValueError, FirebaseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is invalid or expired.",
        ) from exc
    email = token.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An email address is required.")
    email_verified = bool(token.get("email_verified"))
    admin_email = get_settings().admin_email.strip().casefold()
    role: UserRole = "admin" if email_verified and email.casefold() == admin_email else "user"
    return AuthenticatedUser(
        uid=token["uid"],
        email=email,
        role=role,
        email_verified=email_verified,
    )


def get_current_admin(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return user
