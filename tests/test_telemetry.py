import pytest

from signaltrade_trading.telemetry import (
    WORKER_TASK_IN_PROGRESS,
    WORKER_TASK_LAST_SUCCESS,
    WORKER_TASK_RUNS,
    observe_worker_task,
)


def test_observe_worker_task_records_success() -> None:
    task = "test_trading_success"
    before = WORKER_TASK_RUNS.labels(task, "success")._value.get()

    with observe_worker_task(task):
        pass

    assert WORKER_TASK_RUNS.labels(task, "success")._value.get() == before + 1
    assert WORKER_TASK_LAST_SUCCESS.labels(task)._value.get() > 0
    assert WORKER_TASK_IN_PROGRESS.labels(task)._value.get() == 0


def test_observe_worker_task_records_error() -> None:
    task = "test_trading_error"
    before = WORKER_TASK_RUNS.labels(task, "error")._value.get()

    with pytest.raises(RuntimeError):
        with observe_worker_task(task):
            raise RuntimeError("task failed")

    assert WORKER_TASK_RUNS.labels(task, "error")._value.get() == before + 1
    assert WORKER_TASK_IN_PROGRESS.labels(task)._value.get() == 0
