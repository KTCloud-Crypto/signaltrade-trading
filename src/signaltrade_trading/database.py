from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from signaltrade_trading.config import settings
from signaltrade_trading.telemetry import instrument_db_pool

options = ({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
           if settings.database_url.startswith("sqlite") else {
               "pool_size": 2,
               "max_overflow": 2,
               "pool_timeout": 5,
               "pool_pre_ping": True,
           })
engine = create_engine(settings.database_url, **options)
instrument_db_pool(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    with SessionLocal() as db:
        yield db
