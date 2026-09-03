# SignalTrade Trading

전략 신호를 실제 주문 또는 모의 주문으로 처리하고, 실행·체결·거래 기록을 소유하는 서비스입니다. API는 모의계좌와 수동 주문 기능을 제공하고, Worker는 Queue 명령을 소비합니다.

## 주요 책임

- 모의계좌 입금·출금·원장 관리
- Strategy 신호와 수동 주문 요청 검증
- 모의 주문 체결과 Upbit 실전 주문 실행
- 실행 상태, 체결 수량, 수수료, 거래 기록 저장
- 중복 요청 방지와 미완료 실행 복구
- 전략 포지션 일괄 매도와 전략별 수동 매도

## 디렉터리

```text
src/signaltrade_trading/
  api_paper.py        모의계좌 API
  api_public.py       실행 결과·수동 주문 API
  worker.py           Trading Queue 소비 Worker
  paper_execution.py  모의 주문 체결 계산
  live_dispatcher.py  Upbit 실전 주문 처리
  recovery.py         오래된 실행 복구
tests/                주문, 수수료, 복구, 알림 계약 테스트
```

## 다른 서비스와 통신

Strategy가 만든 신호는 Messaging을 거쳐 Trading Queue로 도착합니다. 실전 주문에 필요한 사용자 Upbit 키는 Identity의 내부 API에서만 가져옵니다.

```text
Strategy → Messaging → Trading Queue → Trading Worker
Trading → Outbox → Messaging → Portfolio Queue
Trading → Outbox → Messaging → Notification Queue
```

Portfolio는 Trading 실행 기록을 읽어 포지션을 계산하지만, Trading 소유 테이블을 직접 수정하지 않습니다.

## 로컬 확인

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
```

API와 Worker는 kind에서 분리된 Pod로 실행됩니다. 실전 주문은 연결된 사용자 키와 활성 실전 전략이 있을 때만 실행됩니다.
