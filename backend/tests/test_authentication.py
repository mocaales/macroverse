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


def test_invalid_token_and_missing_email_are_rejected(monkeypatch):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, app: (_ for _ in ()).throw(ValueError("bad token")),
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad")
    with pytest.raises(HTTPException) as invalid:
        dependencies.get_current_user(credentials)
    assert invalid.value.status_code == 401

    monkeypatch.setattr(dependencies.auth, "verify_id_token", lambda token, app: {"uid": "u1"})
    with pytest.raises(HTTPException) as missing_email:
        dependencies.get_current_user(credentials)
    assert missing_email.value.status_code == 403


def test_dependency_factories(monkeypatch):
    database = object()
    pool = object()
    monkeypatch.setattr(dependencies, "get_firestore_client", lambda: database)
    monkeypatch.setattr(dependencies, "get_market_pool", lambda: pool)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: type("Settings", (), {"market_database_batch_size": 10})(),
    )
    assert dependencies.get_db() is database
    assert dependencies.get_portfolio_repository(database).db is database
    assert dependencies.get_market_repository().pool is pool
    monkeypatch.setattr(dependencies, "get_market_pool", lambda: None)
    assert dependencies.get_market_repository() is None
