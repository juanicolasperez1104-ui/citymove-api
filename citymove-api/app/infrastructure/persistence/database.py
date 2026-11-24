from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_session_factory(url: str = "sqlite:///./citymove.db"):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool  # one shared in-memory DB (tests)
    if url.startswith("postgres://"):  # Render/Railway style URL
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql"):
        kwargs["pool_pre_ping"] = True
    engine = create_engine(url, **kwargs)
    from app.infrastructure.persistence import orm  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
