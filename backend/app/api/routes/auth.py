from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import AuthenticatedUser, get_current_user
from app.models.auth import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    return user
