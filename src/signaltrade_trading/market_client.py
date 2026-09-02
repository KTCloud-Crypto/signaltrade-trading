import httpx

from signaltrade_trading.config import settings


class MarketPriceUnavailable(RuntimeError):
    pass


async def get_current_price(market: str) -> float:
    if not settings.internal_service_token:
        raise MarketPriceUnavailable("내부 서비스 토큰이 설정되지 않았습니다.")
    try:
        async with httpx.AsyncClient(timeout=settings.identity_service_timeout_seconds) as client:
            response = await client.get(
                f"{settings.strategy_service_url}/internal/strategy/market-price/{market}",
                headers={"X-SignalTrade-Service-Token": settings.internal_service_token},
            )
    except httpx.HTTPError as error:
        raise MarketPriceUnavailable("Strategy 서비스에서 현재가를 조회할 수 없습니다.") from error
    if response.status_code != 200:
        raise MarketPriceUnavailable("Strategy 서비스에서 현재가를 조회할 수 없습니다.")
    return float(response.json()["price"])
