from psycopg import OperationalError

from app.api.routes.health import health, market_health


class HealthyRepository:
    def healthcheck(self) -> bool:
        return True


class UnavailableRepository:
    def healthcheck(self) -> bool:
        raise OperationalError("database unavailable")


def test_application_health_reports_service_status():
    response = health()

    assert response.status == "ok"
    assert response.service == "macroverse-api"


def test_market_health_reports_unconfigured_database():
    assert market_health(None) == {"status": "not_configured"}


def test_market_health_reports_healthy_database():
    assert market_health(HealthyRepository()) == {"status": "ok"}


def test_market_health_handles_database_errors():
    assert market_health(UnavailableRepository()) == {"status": "unavailable"}
