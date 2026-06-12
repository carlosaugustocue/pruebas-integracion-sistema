import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")
# Normalizar URL async PostgreSQL al driver sincrono
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

_engine_kwargs: dict = {}
if "sqlite" in DATABASE_URL:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in DATABASE_URL:
        from sqlalchemy.pool import StaticPool

        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


# Para SQLite (desarrollo y tests sin Docker), crear tablas al importar el modulo.
# Para PostgreSQL, las tablas se crean en el evento startup de la API o via Alembic.
if "sqlite" in DATABASE_URL:
    init_db()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
