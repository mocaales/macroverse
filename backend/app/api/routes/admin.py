from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import auth as firebase_auth

from app.api.dependencies import (
    AuthenticatedUser,
    get_current_admin,
    get_portfolio_repository,
)
from app.models.auth import AdminUserResponse
from app.models.common import Message
from app.repositories.portfolio import PortfolioRepository
from app.services.admin_users import delete_registered_user, registered_users

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def users(
    _admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
) -> list[AdminUserResponse]:
    return registered_users()


@router.delete(
    "/users/{uid}",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "The administrator account cannot be deleted."},
        status.HTTP_404_NOT_FOUND: {"description": "User not found."},
    },
)
def delete_user(
    uid: str,
    admin: Annotated[AuthenticatedUser, Depends(get_current_admin)],
    repository: Annotated[PortfolioRepository, Depends(get_portfolio_repository)],
) -> Message:
    if uid == admin.uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The administrator account cannot be deleted.",
        )
    try:
        delete_registered_user(uid)
    except firebase_auth.UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from exc

    repository.delete_user_data(uid)
    return Message(message="User deleted.")
