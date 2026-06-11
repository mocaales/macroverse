import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import dependencies


def test_missing_firebase_token_is_rejected():
    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(None)

    assert error.value.status_code == 401


def test_valid_firebase_token_returns_uid_and_email(monkeypatch):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, app: {"uid": "firebase-user-123", "email": "trader@example.com"},
    )

    user = dependencies.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token"))

    assert user.uid == "firebase-user-123"
    assert user.email == "trader@example.com"
