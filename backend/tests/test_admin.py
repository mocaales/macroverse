from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from firebase_admin import auth as firebase_auth

from app.api.dependencies import AuthenticatedUser
from app.api.routes import admin
from app.services import admin_users


def _admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="admin-uid",
        email="admin@example.com",
        role="admin",
        email_verified=True,
    )


def test_registered_users_lists_admin_first(monkeypatch):
    metadata = SimpleNamespace(
        creation_timestamp=1_700_000_000_000,
        last_sign_in_timestamp=None,
    )
    records = [
        SimpleNamespace(
            uid="user-uid",
            email="user@example.com",
            email_verified=True,
            disabled=False,
            user_metadata=metadata,
        ),
        SimpleNamespace(
            uid="admin-uid",
            email="admin@example.com",
            email_verified=True,
            disabled=False,
            user_metadata=metadata,
        ),
    ]
    page = SimpleNamespace(iterate_all=lambda: iter(records))
    monkeypatch.setattr(admin_users, "get_firebase_app", lambda: object())
    monkeypatch.setattr(admin_users.auth, "list_users", lambda app: page)
    monkeypatch.setattr(
        admin_users,
        "get_settings",
        lambda: SimpleNamespace(admin_email="admin@example.com"),
    )

    users = admin_users.registered_users()

    assert [user.role for user in users] == ["admin", "user"]
    assert users[0].created_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)


def test_admin_routes_list_and_delete_users(monkeypatch):
    listed = []
    deleted = []

    class Repository:
        def delete_user_data(self, uid):
            deleted.append(("firestore", uid))

    monkeypatch.setattr(admin, "registered_users", lambda: listed)
    monkeypatch.setattr(
        admin,
        "delete_registered_user",
        lambda uid: deleted.append(("firebase", uid)),
    )

    assert admin.users(_admin()) == []
    result = admin.delete_user("user-uid", _admin(), Repository())

    assert result.message == "User deleted."
    assert deleted == [("firebase", "user-uid"), ("firestore", "user-uid")]


def test_admin_cannot_delete_self():
    with pytest.raises(HTTPException) as error:
        admin.delete_user("admin-uid", _admin(), object())

    assert error.value.status_code == 400


def test_delete_missing_user_returns_not_found(monkeypatch):
    monkeypatch.setattr(
        admin,
        "delete_registered_user",
        lambda uid: (_ for _ in ()).throw(firebase_auth.UserNotFoundError(uid)),
    )

    with pytest.raises(HTTPException) as error:
        admin.delete_user("missing-user", _admin(), object())

    assert error.value.status_code == 404
    assert error.value.detail == "User not found."
