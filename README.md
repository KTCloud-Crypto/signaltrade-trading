# SignalTrade Trading

모의·실전 주문, 체결 기록, 모의계좌를 맡는 서비스입니다.

```text
src/signaltrade_trading/  주문 API·Worker·모의계좌
tests/                    주문과 복구 테스트
```

Strategy 신호와 수동 주문 명령을 Queue에서 받아 처리합니다. 거래소 키는 Identity 내부 API에서만 조회하고, 체결 결과는 Outbox로 Portfolio와 Notification에 전달합니다.
