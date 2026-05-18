from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.engine import Engine
from coach.config import Settings
import coach.models  # noqa: F401  — register tables on SQLModel.metadata


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    return engine


def session_for(engine: Engine) -> Session:
    return Session(engine)
