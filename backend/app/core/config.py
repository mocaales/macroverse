from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Macroverse API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    firebase_project_id: str = ""
    firebase_service_account_base64: str = ""
    market_database_url: str = ""
    market_database_pool_min_size: int = 1
    market_database_pool_max_size: int = 5
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
