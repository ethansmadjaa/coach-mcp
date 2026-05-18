from sqlmodel import Session, create_engine
from sqlalchemy.engine import Engine
from coach.config import Settings


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return create_engine(url, pool_pre_ping=True)


def session_for(engine: Engine) -> Session:
    return Session(engine)
