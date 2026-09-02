from dataclasses import dataclass
from signaltrade_trading.dispatcher import dispatch_signal
from signaltrade_trading.message_contract import MessageEnvelope


@dataclass(frozen=True, slots=True)
class TradingCommandResult:
    signal_id: int
    execution_count: int


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
