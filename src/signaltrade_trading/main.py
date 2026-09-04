from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from starlette.responses import Response

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.api_paper import router as paper_router
from signaltrade_trading.api_manual import internal_router as internal_manual_router, router as manual_router
from signaltrade_trading.api_history import strategy_router as history_router, trade_router

app = FastAPI(title="SignalTrade Trading API", version="1.0.0")
app.include_router(paper_router)
app.include_router(manual_router)
app.include_router(internal_manual_router)
app.include_router(history_router)
app.include_router(trade_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "trading"}


@app.get("/ready")
def ready() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
