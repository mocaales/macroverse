from datetime import UTC, datetime

from firebase_admin import auth

from app.core.config import get_settings
from app.core.firebase import get_firebase_app
from app.models.auth import AdminUserResponse, UserRole


def _timestamp(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value / 1000, tz=UTC) if value else None


def _role(email: str | None) -> UserRole:
    admin_email = get_settings().admin_email.strip().casefold()
    return "admin" if email and email.casefold() == admin_email else "user"


def registered_users() -> list[AdminUserResponse]:
    users = []
    page = auth.list_users(app=get_firebase_app())
    for record in page.iterate_all():
        users.append(
            AdminUserResponse(
                uid=record.uid,
                email=record.email,
                role=_role(record.email),
                email_verified=record.email_verified,
                disabled=record.disabled,
                created_at=_timestamp(record.user_metadata.creation_timestamp),
                last_sign_in_at=_timestamp(record.user_metadata.last_sign_in_timestamp),
            )
        )
    return sorted(users, key=lambda user: (user.role != "admin", (user.email or "").casefold()))


def delete_registered_user(uid: str) -> None:
    auth.delete_user(uid, app=get_firebase_app())
