import time
from contextlib import contextmanager
from collections.abc import Iterator

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("signaltrade_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram("signaltrade_http_request_duration_seconds", "HTTP request latency", ["method", "route"])
HTTP_IN_PROGRESS = Gauge("signaltrade_http_requests_in_progress", "Currently running HTTP requests")
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
