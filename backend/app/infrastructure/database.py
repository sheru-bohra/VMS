from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.infrastructure.database_engine import build_engine, validate_production_database_policy

Base = declarative_base()

_engine, _dialect = build_engine()
validate_production_database_policy(settings.resolved_database_url())

engine = _engine
database_dialect = _dialect
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def dispose_engine() -> None:
    engine.dispose()
