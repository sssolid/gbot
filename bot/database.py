# File: database.py
# Location: /bot/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from models import Base
from config import Config
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager"""

    def __init__(self, url=None):
        self.url = url or Config.DATABASE_URL
        self.engine = create_engine(
            self.url,
            echo=Config.DEBUG_MODE,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.Session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))

    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")

    def drop_tables(self):
        """Drop all tables (use with caution)"""
        Base.metadata.drop_all(self.engine)
        logger.warning("Database tables dropped")

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def get_session(self):
        """Get a new session"""
        return self.Session()

    def close(self):
        """Close all sessions"""
        self.Session.remove()
        self.engine.dispose()
        logger.info("Database connections closed")


# Global database instance
db = Database()