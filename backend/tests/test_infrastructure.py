import base64
import json

from app.api.dependencies import AuthenticatedUser
from app.api.routes.auth import me
from app.core import firebase, market_database


def test_auth_route_and_model_modules_import():
    user = AuthenticatedUser(uid="u1", email="user@example.com")
    assert me(user) is user
    from app.api.router import api_router
    from app.models.auth import UserResponse
    from app.models.charts import ChartDefinition, ChartSeries, SeriesPoint

    assert api_router.routes
    assert UserResponse(
        uid="u1",
        email="user@example.com",
        role="user",
        email_verified=True,
    ).uid == "u1"
    point = SeriesPoint(date="2026-01-01", value=1)
    assert ChartSeries(name="x", points=[point]).points[0].value == 1
    assert ChartDefinition(
        name="x", slug="x", category="Macro", quick=[], assets=[], summary="x", available=True
    ).available


def test_firebase_credentials_app_and_client(monkeypatch):
    payload = {"project_id": "macroverse"}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    settings = type(
        "Settings",
        (),
        {"firebase_service_account_base64": encoded, "firebase_project_id": "macroverse"},
    )()
    monkeypatch.setattr(firebase, "get_settings", lambda: settings)
    certificate = object()
    monkeypatch.setattr(firebase.credentials, "Certificate", lambda value: certificate if value == payload else None)
    assert firebase._credential() is certificate

    monkeypatch.setattr(firebase.firebase_admin, "get_app", lambda: (_ for _ in ()).throw(ValueError()))
    app = object()
    monkeypatch.setattr(firebase.firebase_admin, "initialize_app", lambda credential, options: app)
    firebase.get_firebase_app.cache_clear()
    assert firebase.get_firebase_app() is app
    monkeypatch.setattr(firebase.firestore, "client", lambda app: "client")
    firebase.get_firestore_client.cache_clear()
    assert firebase.get_firestore_client() == "client"


def test_empty_firebase_credentials_and_market_pool(monkeypatch):
    monkeypatch.setattr(
        firebase,
        "get_settings",
        lambda: type("Settings", (), {"firebase_service_account_base64": "", "firebase_project_id": ""})(),
    )
    assert firebase._credential() is None

    settings = type(
        "Settings",
        (),
        {
            "market_database_conninfo": "",
            "market_database_pool_min_size": 1,
            "market_database_pool_max_size": 2,
        },
    )()
    monkeypatch.setattr(market_database, "get_settings", lambda: settings)
    market_database.get_market_pool.cache_clear()
    assert market_database.get_market_pool() is None
    settings.market_database_conninfo = "postgresql://example"
    monkeypatch.setattr(market_database, "ConnectionPool", lambda **kwargs: kwargs)
    market_database.get_market_pool.cache_clear()
    assert market_database.get_market_pool()["conninfo"] == "postgresql://example"
