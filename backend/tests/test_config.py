import secrets
import socket

from psycopg.conninfo import conninfo_to_dict

from app.core.config import Settings


def test_database_conninfo_is_built_from_postgres_environment():
    host = secrets.token_hex(8)
    database = secrets.token_hex(8)
    user = secrets.token_hex(8)
    password = secrets.token_urlsafe(24)
    with socket.socket() as available_port:
        available_port.bind(("", 0))
        port = available_port.getsockname()[1]
    settings = Settings(
        _env_file=None,
        postgres_host=host,
        postgres_port=port,
        postgres_db=database,
        postgres_user=user,
        postgres_password=password,
    )

    conninfo = conninfo_to_dict(settings.market_database_conninfo)

    assert conninfo == {
        "host": host,
        "port": str(port),
        "dbname": database,
        "user": user,
        "password": password,
    }


def test_managed_database_url_takes_precedence():
    managed_connection = secrets.token_urlsafe(24)
    settings = Settings(
        _env_file=None,
        market_database_url=managed_connection,
        postgres_host=secrets.token_hex(8),
        postgres_port=1,
        postgres_db=secrets.token_hex(8),
        postgres_user=secrets.token_hex(8),
        postgres_password=secrets.token_urlsafe(24),
    )

    assert settings.market_database_conninfo == managed_connection


def test_incomplete_database_environment_disables_pool():
    settings = Settings(_env_file=None, postgres_host=secrets.token_hex(8))

    assert settings.market_database_conninfo == ""


def test_cors_is_closed_by_default_and_parses_configured_origins():
    assert Settings(_env_file=None).cors_origin_list == []

    settings = Settings(
        _env_file=None,
        cors_origins="https://app.example.com, https://admin.example.com,",
    )

    assert settings.cors_origin_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
