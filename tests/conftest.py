import os

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")


@pytest.fixture(autouse=True)
def reset_database():
    from signaltrade_trading.database import Base, engine
    import signaltrade_trading.models  # noqa: F401

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
