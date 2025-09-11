from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from functools import wraps
from sqlmodel import SQLModel
from utils.settings import get_settings
from contextlib import contextmanager

settings = get_settings()


@lru_cache
def init() -> sessionmaker:
    """
    Initialize the database session.
    This function creates a new SQLAlchemy engine and sessionmaker.
    It uses the database URL from the settings.
    """
    db_url = settings.API_DATABASE_URL
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> sessionmaker:
    """
    Get a new database session.
    This function creates a new session using the sessionmaker.
    It is used to interact with the database.
    """
    instance = init()
    return instance()


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
