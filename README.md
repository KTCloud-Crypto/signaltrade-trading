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
