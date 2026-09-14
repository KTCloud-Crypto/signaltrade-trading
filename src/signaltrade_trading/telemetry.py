import time
from contextlib import contextmanager
from collections.abc import Iterator

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("signaltrade_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram("signaltrade_http_request_duration_seconds", "HTTP request latency", ["method", "route"])
HTTP_IN_PROGRESS = Gauge("signaltrade_http_requests_in_progress", "Currently running HTTP requests")
EXTERNAL_REQUESTS = Counter(
    "signaltrade_external_requests_total",
    "External API requests",
    ["provider", "operation", "outcome"],
)
EXTERNAL_DURATION = Histogram(
    "signaltrade_external_request_duration_seconds",
    "External API latency",
    ["provider", "operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
DB_POOL_CONNECTIONS = Gauge(
    "signaltrade_db_pool_connections",
    "SQLAlchemy database pool connections by state",
    ["state"],
)
WORKER_TASK_RUNS = Counter(
    "signaltrade_worker_task_runs_total", "Worker task executions", ["task", "result"]
)
WORKER_TASK_DURATION = Histogram(
    "signaltrade_worker_task_duration_seconds", "Worker task execution time", ["task"]
)
WORKER_TASK_LAST_SUCCESS = Gauge(
    "signaltrade_worker_task_last_success_timestamp_seconds",
    "Unix timestamp of the last successful worker task execution",
    ["task"],
)
WORKER_TASK_IN_PROGRESS = Gauge(
    "signaltrade_worker_task_in_progress", "Worker tasks currently running", ["task"]
)


def instrument_db_pool(engine) -> None:
    """Expose live QueuePool state; StaticPool used by tests has no pool counters."""
    pool = engine.pool
    metrics = {
        "size": getattr(pool, "size", None),
        "checked_in": getattr(pool, "checkedin", None),
        "checked_out": getattr(pool, "checkedout", None),
        "overflow": getattr(pool, "overflow", None),
    }
    for state, callback in metrics.items():
        if callable(callback):
            DB_POOL_CONNECTIONS.labels(state).set_function(callback)


@contextmanager
def observe_external_call(provider: str, operation: str) -> Iterator[None]:
    started = time.perf_counter()
    outcome = "success"
    try:
        yield
    except TimeoutError:
        outcome = "timeout"
        raise
    except Exception as error:
        status = getattr(error, "code", None)
        outcome = f"http_{status}" if isinstance(status, int) else "error"
        raise
    finally:
        EXTERNAL_DURATION.labels(provider, operation).observe(time.perf_counter() - started)
        EXTERNAL_REQUESTS.labels(provider, operation, outcome).inc()


@contextmanager
def observe_worker_task(task: str) -> Iterator[None]:
    started = time.perf_counter()
    WORKER_TASK_IN_PROGRESS.labels(task).inc()
    try:
        yield
    except Exception:
        WORKER_TASK_RUNS.labels(task, "error").inc()
        raise
    else:
        WORKER_TASK_RUNS.labels(task, "success").inc()
        WORKER_TASK_LAST_SUCCESS.labels(task).set(time.time())
    finally:
        WORKER_TASK_DURATION.labels(task).observe(time.perf_counter() - started)
        WORKER_TASK_IN_PROGRESS.labels(task).dec()


def instrument_http(app) -> None:
    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = time.perf_counter()
        HTTP_IN_PROGRESS.inc()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_DURATION.labels(request.method, route).observe(time.perf_counter() - started)
            HTTP_IN_PROGRESS.dec()
