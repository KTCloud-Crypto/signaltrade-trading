from dataclasses import dataclass
from signaltrade_trading.dispatcher import dispatch_manual_request, dispatch_signal
from signaltrade_trading.message_contract import MessageEnvelope


@dataclass(frozen=True, slots=True)
class TradingCommandResult:
    signal_id: int | None
    execution_count: int
    execution_request_id: int | None = None


def execute_strategy_signal(envelope: MessageEnvelope) -> TradingCommandResult:
    if envelope.message_type != "StrategySignalCreated":
        raise ValueError(f"unsupported trading message type: {envelope.message_type}")
    signal_id = envelope.payload.get("signal_id")
    user_id = envelope.payload.get("target_user_id")
    mode = envelope.payload.get("target_mode")
    if not isinstance(signal_id, int) or signal_id <= 0:
        raise ValueError("StrategySignalCreated.signal_id must be a positive integer")
    if user_id is not None and (not isinstance(user_id, int) or user_id <= 0):
        raise ValueError("target_user_id must be a positive integer or null")
    if mode not in {None, "simulated", "live"}:
        raise ValueError("target_mode must be simulated, live, or null")
    return TradingCommandResult(signal_id, dispatch_signal(signal_id, user_id, mode))


def execute_manual_liquidation(envelope: MessageEnvelope) -> TradingCommandResult:
    if envelope.message_type != "ManualLiquidationRequested":
        raise ValueError(f"unsupported trading message type: {envelope.message_type}")
    request_id = envelope.payload.get("execution_request_id")
    if not isinstance(request_id, int) or request_id <= 0:
        raise ValueError(
            "ManualLiquidationRequested.execution_request_id must be a positive integer"
        )
    return TradingCommandResult(
        signal_id=None,
        execution_count=dispatch_manual_request(request_id),
        execution_request_id=request_id,
    )
