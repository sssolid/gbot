# File: database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from models import Base
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager"""

    def __init__(self):
        self.engine = None
        self.Session = None
        self.url = None

    def init_app(self, config):
        """Initialize the database with configuration"""
        self.url = config.DATABASE_URL
        self.engine = create_engine(
            self.url,
            echo=config.DEBUG_MODE,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.Session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))
        logger.info(f"Database initialized with URL: {self.url}")

    def create_tables(self):
        import models
        import models_game_db
        import models_rpg

        if not self.engine:
            raise RuntimeError("Database not initialized. Call init_app(config) first.")
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")

    def drop_tables(self):
        if not self.engine:
            raise RuntimeError("Database not initialized. Call init_app(config) first.")
        Base.metadata.drop_all(self.engine)
        logger.warning("Database tables dropped")

    @contextmanager
    def session_scope(self):
        if not self.Session:
            raise RuntimeError("Database not initialized. Call init_app(config) first.")
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
        if not self.Session:
            raise RuntimeError("Database not initialized. Call init_app(config) first.")
        return self.Session()

    def close(self):
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connections closed")


# Global instance, uninitialized
db = Database()
