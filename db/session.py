from contextlib import contextmanager
from functools import lru_cache, wraps
from sqlalchemy import create_engine, schema
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel
from typing import Generator
from utils.settings import get_settings


settings = get_settings()


@lru_cache
def get_sessionmaker() -> sessionmaker:
    """
    Get a SQLAlchemy sessionmaker.
    Uses lru_cache to ensure only one instance is created.
    """

    engine = create_engine(settings.API_DATABASE_URL)

    connection = engine.connect()
    if connection.dialect.has_schema(connection, "transcribe"):
        engine.execute(schema.CreateSchema("transcribe"))

    SQLModel.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.
    """

    db_session_factory = get_sessionmaker()
    session: Session = db_session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.commit()
        session.close()


def handle_database_errors(func) -> callable:
    """
    Decorator to handle database errors.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        session = None
        try:
            session = get_session()
            kwargs["session"] = session

            return func(*args, **kwargs)
        except Exception as e:
            print(f"Database error has occurred: {e}")
            raise
        finally:
            if session:
                session.close()

    return wrapper


@contextmanager
def sqla_session():
    """
    Provide a transactional scope around a series of operations.
    """

    session = get_session()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
