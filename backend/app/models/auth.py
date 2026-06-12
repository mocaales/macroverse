from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

UserRole = Literal["admin", "user"]


class UserResponse(BaseModel):
    uid: str
    email: EmailStr
    role: UserRole
    email_verified: bool


class AdminUserResponse(BaseModel):
    uid: str
    email: EmailStr | None
    role: UserRole
    email_verified: bool
    disabled: bool
    created_at: datetime | None = None
    last_sign_in_at: datetime | None = None
