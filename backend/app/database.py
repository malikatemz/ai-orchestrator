from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


def build_engine(database_url: str):
    """Build SQLAlchemy engine with appropriate connect args."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def build_session(engine) -> sessionmaker:
    """Build sessionmaker for database sessions."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


engine = build_engine(str(settings.database_url))
SessionLocal = build_session(engine)


def get_db() -> Session:
    """Dependency to get database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_override=None):
    """Initialize database tables."""
    from .models import Base

    Base.metadata.create_all(bind=engine_override or engine)
