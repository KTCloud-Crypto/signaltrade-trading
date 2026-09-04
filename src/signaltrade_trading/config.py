from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql://signaltrade:signaltrade-local@localhost:5432/signaltrade"
    identity_service_url: str = "http://identity-api:8000"
    strategy_service_url: str = "http://strategy-api:8000"
    portfolio_service_url: str = "http://portfolio-api:8000"
    identity_service_timeout_seconds: float = 5.0
    internal_service_token: str = ""
    aws_region: str = "ap-northeast-2"
    # LocalStack에서만 .env로 테스트 키를 주입합니다. EKS에서는 Pod Identity를 사용합니다.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    sqs_endpoint_url: str | None = None
    sqs_trading_command_queue_name: str = "signaltrade-trading-commands"
    sqs_trading_visibility_timeout_seconds: int = 300
    metrics_enabled: bool = True
    trading_metrics_port: int = 9102
    stale_execution_seconds: int = 120
    order_reconciliation_seconds: int = 10
    execution_recovery_seconds: int = 30


settings = Settings()
