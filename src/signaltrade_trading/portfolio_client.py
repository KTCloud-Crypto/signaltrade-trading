import httpx

from signaltrade_trading.config import settings


class PortfolioUnavailable(RuntimeError):
    pass


def get_reconciliation_differences(user_id: int) -> dict[str, float]:
    if not settings.internal_service_token:
        raise PortfolioUnavailable("내부 서비스 토큰이 설정되지 않았습니다.")
    try:
        response = httpx.get(
            f"{settings.portfolio_service_url.rstrip('/')}/internal/portfolio/users/{user_id}/reconciliation-state",
            headers={"X-SignalTrade-Service-Token": settings.internal_service_token},
            timeout=settings.identity_service_timeout_seconds,
        )
    except httpx.HTTPError as error:
        raise PortfolioUnavailable("Portfolio 서비스에서 잔고 차이를 조회할 수 없습니다.") from error
    if response.status_code != 200:
        raise PortfolioUnavailable("Portfolio 서비스에서 잔고 차이를 조회할 수 없습니다.")
    return {
        currency: float(values["difference"])
        for currency, values in response.json().items()
    }
