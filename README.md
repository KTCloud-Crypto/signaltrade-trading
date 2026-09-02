# signaltrade-trading

SignalTrade의 주문 실행과 체결 이력을 소유하는 독립 서비스입니다.

## Ownership

- `strategy_execution`, `trading_execution_request`, `trade`
- `paper_account`, `paper_ledger`
- Strategy 신호와 수동 청산 명령 소비
- 모의 주문 및 Upbit 실주문 실행·정산

Strategy 카탈로그/구독과 사용자 인증은 소유하지 않습니다. 공유 PostgreSQL을
사용하는 전환 기간에도 다른 서비스 소유 테이블에는 직접 쓰지 않습니다.

## Local development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

실전 거래 자격증명은 로컬 DB에서 직접 읽지 않고 Identity의 내부 API에서 조회합니다.
두 런타임에 동일한 `INTERNAL_SERVICE_TOKEN`을 주입해야 하며 반환된 키는 메모리에서만
주문 사전검증과 주문 요청에 사용합니다.

수동 청산 API는 `TradingExecutionRequest`와 `ManualLiquidationRequested` Outbox를
같은 트랜잭션에 저장합니다. Worker는 이 명령을 소비해 자동매매와 같은 모의·실전
주문 안전장치를 거치며, `Idempotency-Key`로 API 재요청을 중복 제거할 수 있습니다.
