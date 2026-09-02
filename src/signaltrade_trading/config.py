from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql://signaltrade:signaltrade-local@localhost:5432/signaltrade"
    identity_service_url: str = "http://identity-api:8000"
    strategy_service_url: str = "http://strategy-api:8000"
    identity_service_timeout_seconds: float = 5.0


settings = Settings()
