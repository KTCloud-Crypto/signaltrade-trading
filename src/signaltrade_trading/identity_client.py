from __future__ import annotations

import httpx
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from signaltrade_trading.config import settings


class AuthenticatedUser(BaseModel):
    id: int
    username: str
    nickname: str
    bot_enabled: bool
    execution_mode: str
    live_trading_enabled: bool


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="인증 토큰이 필요합니다.",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        response = httpx.get(
            f"{settings.identity_service_url}/internal/auth/me",
            headers={"Authorization": authorization},
            timeout=settings.identity_service_timeout_seconds,
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Identity 서비스를 사용할 수 없습니다.") from error
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="유효하지 않은 인증 토큰입니다.",
                            headers={"WWW-Authenticate": "Bearer"})
    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Identity 서비스를 사용할 수 없습니다.")
    return AuthenticatedUser.model_validate(response.json())
