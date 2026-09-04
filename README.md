# SignalTrade Trading

Strategy가 만든 신호를 실제 주문 또는 모의 주문으로 실행하는 서비스입니다. 주문 요청부터 체결 결과와 거래 원장까지 실행 과정의 기준 데이터를 소유합니다.

## 주요 역할

- Trading Queue에서 전략 신호와 실행 명령 소비
- 사용자 모드에 따른 모의투자·실전투자 분기
- 주문 예산, 중복 요청과 실행 가능 상태 검증
- 모의 주문 체결, 수수료와 잔고 계산
- Upbit API를 통한 실전 매수·매도 주문
- 실행 요청, 체결 수량, 가격, 수수료와 거래 내역 저장
- 모의계좌 입금·출금과 변경 원장 관리
- 전략별 수동 매도와 전체 포지션 청산
- 처리 도중 중단된 실행의 상태 확인과 복구

Trading은 **실제로 주문을 수행하고 결과를 기록**합니다. 전략 조건 계산은 Strategy, 보유 자산의 종합 조회와 실제 잔고 비교는 Portfolio가 담당합니다.

## Write 권한이 있는 테이블

- `trading_execution_request`: 중복 방지용 주문 실행 요청
- `strategy_execution`: 전략 신호의 실행 상태와 결과
- `trade`: 실제 또는 모의 체결·거래 기록
- `paper_account`: 사용자의 모의투자 계좌
- `paper_ledger`: 모의계좌 입출금과 잔고 변경 원장
- `message_outbox`: 후속 서비스에 전달할 이벤트

Strategy의 신호와 설정, Identity의 사용자 정보는 조회만 하고 직접 변경하지 않습니다.

## HTTP 통신

Frontend에 거래 내역, 실행 결과, 모의계좌, 수동 주문과 청산 API를 제공합니다. 실전 주문 직전에는 Identity 내부 HTTP API로 사용자의 복호화된 Upbit Key를 요청합니다.

중단된 주문을 복구할 때는 거래소 상태와 함께 Portfolio 내부 HTTP API의 현재 포지션 정보를 확인합니다. 전달받은 거래소 Key는 주문 처리에만 사용하며 DB나 로그에 다시 저장하지 않습니다.

## Queue 통신

Trading Worker가 소비하는 Trading Queue 이벤트는 다음과 같습니다.

- `StrategySignalCreated`: Strategy가 만든 주문 신호
- `PositionReconciled`: Portfolio가 확정한 수량 조정
- `ManualLiquidationRequested`: API가 만든 비동기 청산 요청

처리 결과로 전략 예산이 바뀌면 `AllocationChanged`를 Strategy Queue로 보내고, 사용자에게 알려야 할 내용은 `NotificationRequested`로 Notification Queue에 보냅니다. 두 이벤트 모두 `message_outbox`와 Messaging을 거쳐 전달됩니다. Redis는 사용하지 않습니다.
