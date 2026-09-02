from fastapi import FastAPI
from sqlalchemy import text

from signaltrade_trading.database import SessionLocal

app = FastAPI(title="SignalTrade Trading API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "trading"}


@app.get("/ready")
def ready() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
