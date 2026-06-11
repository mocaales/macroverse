from functools import lru_cache

from psycopg.conninfo import make_conninfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Macroverse API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = ""
    firebase_project_id: str = ""
    firebase_service_account_base64: str = ""
    market_database_url: str = ""
    postgres_host: str = ""
    postgres_port: int | None = None
    postgres_db: str = ""
    postgres_user: str = ""
    postgres_password: str = ""
    market_database_pool_min_size: int = 1
    market_database_pool_max_size: int = 5
    market_database_batch_size: int = 25
    coinmetrics_api_base_url: str = "https://community-api.coinmetrics.io/v4"
    fred_api_key: str = ""
    cryptoquant_access_token: str = ""
    cryptoquant_series_json: str = "[]"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def market_database_conninfo(self) -> str:
        if self.market_database_url:
            return self.market_database_url
        if not all(
            (
                self.postgres_host,
                self.postgres_port,
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
            )
        ):
            return ""
        return make_conninfo(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
