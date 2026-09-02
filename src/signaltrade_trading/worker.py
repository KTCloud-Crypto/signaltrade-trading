import logging
import signal
import threading
from prometheus_client import start_http_server

import signaltrade_trading.models  # noqa: F401
from signaltrade_trading.config import settings
from signaltrade_trading.sqs import SqsQueueAdapter
from signaltrade_trading.trading_commands import execute_strategy_signal

logger = logging.getLogger(__name__)


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    if settings.metrics_enabled:
        start_http_server(settings.trading_metrics_port)
    queue = SqsQueueAdapter.from_settings()
    logger.info("Trading worker started")
    while not stop.is_set():
        try:
            for message in queue.receive():
                result = execute_strategy_signal(message.envelope)
                queue.acknowledge(message)
                logger.info("Trading signal processed: signal_id=%s executions=%s",
                            result.signal_id, result.execution_count)
        except Exception:
            logger.exception("Trading message failed; leaving it unacknowledged")
            stop.wait(1)


def run():
    logging.basicConfig(level=logging.INFO)
    main()


if __name__ == "__main__":
    run()
