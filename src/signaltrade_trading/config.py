from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql://signaltrade:signaltrade-local@localhost:5432/signaltrade"
    identity_service_url: str = "http://identity-api:8000"
    strategy_service_url: str = "http://strategy-api:8000"
    identity_service_timeout_seconds: float = 5.0
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    sqs_endpoint_url: str | None = None
    sqs_trading_command_queue_name: str = "signaltrade-trading-commands"
    sqs_trading_visibility_timeout_seconds: int = 300
    metrics_enabled: bool = True
    trading_metrics_port: int = 9102
    stale_execution_seconds: int = 120


settings = Settings()
