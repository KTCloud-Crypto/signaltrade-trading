import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("signaltrade_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram("signaltrade_http_request_duration_seconds", "HTTP request latency", ["method", "route"])
HTTP_IN_PROGRESS = Gauge("signaltrade_http_requests_in_progress", "Currently running HTTP requests")


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
