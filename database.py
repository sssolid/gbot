"""
Database models and setup for the Guild Management Bot - FIXED VERSION
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, 
    JSON, String, Text, Index, text
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class GuildConfig(Base):
    __tablename__ = 'guild_configs'
    
    guild_id = Column(BigInteger, primary_key=True)
    default_member_role_id = Column(BigInteger, nullable=True)
    welcome_channel_id = Column(BigInteger, nullable=True)
    logs_channel_id = Column(BigInteger, nullable=True)
    announcements_channel_id = Column(BigInteger, nullable=True)
    admin_dashboard_channel_id = Column(BigInteger, nullable=True)
    admin_dashboard_message_id = Column(BigInteger, nullable=True)
    member_hub_channel_id = Column(BigInteger, nullable=True)
    member_hub_message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConfigKV(Base):
    __tablename__ = 'config_kv'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    key = Column(String(255), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_key', 'guild_id', 'key'),
    )


class OnboardingQuestion(Base):
    __tablename__ = 'onboarding_questions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    qid = Column(String(100), nullable=False)  # Unique identifier for the question
    prompt = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # 'single_select' or 'text'
    required = Column(Boolean, default=True)
    options = Column(JSON, nullable=True)  # For single_select questions
    map_to = Column(String(100), nullable=False)  # Key for rules engine
    position = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_is_active', 'guild_id', 'is_active'),
        Index('idx_guild_position', 'guild_id', 'position'),
    )


class OnboardingRule(Base):
    __tablename__ = 'onboarding_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    when_conditions = Column(JSON, nullable=False)  # Array of {key, value} conditions
    suggest_roles = Column(JSON, nullable=False)  # Array of role IDs or names
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_active_rules', 'guild_id', 'is_active'),
    )


class OnboardingSession(Base):
    __tablename__ = 'onboarding_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    state = Column(String(50), default='in_progress', index=True)  # 'in_progress', 'completed', 'approved', 'denied'
    answers = Column(JSON, default=dict)  # {question_qid: answer}
    suggestion = Column(JSON, nullable=True)  # Suggested roles from rules engine
    denial_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(BigInteger, nullable=True)  # User ID of who approved/denied
    
    __table_args__ = (
        Index('idx_guild_state', 'guild_id', 'state'),
        Index('idx_guild_user_state', 'guild_id', 'user_id', 'state'),
        Index('idx_completed_at', 'completed_at'),
    )


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_user', 'guild_id', 'user_id'),
    )


class Character(Base):
    __tablename__ = 'characters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    archetype = Column(String(255), nullable=True)
    build_notes = Column(Text, nullable=True)
    is_main = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_user_char', 'guild_id', 'user_id'),
        Index('idx_guild_user_main', 'guild_id', 'user_id', 'is_main'),
    )


class Poll(Base):
    __tablename__ = 'polls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True, index=True)
    creator_id = Column(BigInteger, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    options = Column(JSON, nullable=False)  # Array of option strings
    anonymous = Column(Boolean, default=False)
    multiple_choice = Column(Boolean, default=False)
    ends_at = Column(DateTime, nullable=True, index=True)
    closed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_active', 'guild_id', 'closed'),
        Index('idx_ends_at', 'ends_at'),
    )


class PollVote(Base):
    __tablename__ = 'poll_votes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    option_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    poll = relationship("Poll", backref="votes")
    
    __table_args__ = (
        Index('idx_poll_user', 'poll_id', 'user_id'),
    )


class ModerationIncident(Base):
    __tablename__ = 'moderation_incidents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    type = Column(String(50), nullable=False, index=True)  # 'spam', 'swear', 'manual_warn', 'manual_timeout'
    reason = Column(Text, nullable=True)
    message_snapshot = Column(JSON, nullable=True)
    action_taken = Column(String(100), nullable=True, index=True)  # 'delete', 'warn', 'timeout'
    moderator_id = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_guild_type', 'guild_id', 'type'),
        Index('idx_guild_created', 'guild_id', 'created_at'),
        Index('idx_user_incidents', 'guild_id', 'user_id', 'created_at'),
    )


class Announcement(Base):
    __tablename__ = 'announcements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    author_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    content = Column(Text, nullable=False)
    scheduled_for = Column(DateTime, nullable=True, index=True)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_guild_scheduled', 'guild_id', 'scheduled_for'),
        Index('idx_scheduled_pending', 'scheduled_for'),
    )


# Database connection and session management
_engine = None
_session_maker = None


async def init_database(database_url: str):
    """Initialize the database connection and create tables."""
    global _engine, _session_maker
    
    # Convert SQLite URL for async if needed
    if database_url.startswith('sqlite:///'):
        database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    
    _engine = create_async_engine(
        database_url, 
        echo=False,
        pool_pre_ping=True,  # Enable connection health checks
        pool_recycle=3600,   # Recycle connections every hour
    )
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    
    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database initialized successfully")


def get_session() -> AsyncSession:
    """Get a database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_maker()


async def close_database():
    """Close the database connection."""
    global _engine
    if _engine:
        await _engine.dispose()
        print("Database connection closed")


# Utility functions for common queries
async def get_guild_config(guild_id: int) -> Optional[GuildConfig]:
    """Get guild configuration."""
    async with get_session() as session:
        result = await session.get(GuildConfig, guild_id)
        return result


async def create_or_update_guild_config(guild_id: int, **kwargs) -> GuildConfig:
    """Create or update guild configuration."""
    async with get_session() as session:
        config = await session.get(GuildConfig, guild_id)
        
        if not config:
            config = GuildConfig(guild_id=guild_id, **kwargs)
            session.add(config)
        else:
            for key, value in kwargs.items():
                setattr(config, key, value)
            config.updated_at = datetime.utcnow()
        
        await session.commit()
        await session.refresh(config)
        return config


async def get_pending_onboarding_sessions(guild_id: int, limit: int = 50) -> List[OnboardingSession]:
    """Get pending onboarding sessions for a guild."""
    from sqlalchemy import select, and_
    
    async with get_session() as session:
        result = await session.execute(
            select(OnboardingSession)
            .where(
                and_(
                    OnboardingSession.guild_id == guild_id,
                    OnboardingSession.state == 'completed'
                )
            )
            .order_by(OnboardingSession.completed_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def get_user_onboarding_session(guild_id: int, user_id: int, state: str = 'in_progress') -> Optional[OnboardingSession]:
    """Get user's onboarding session in a specific state."""
    from sqlalchemy import select, and_
    
    async with get_session() as session:
        result = await session.execute(
            select(OnboardingSession)
            .where(
                and_(
                    OnboardingSession.guild_id == guild_id,
                    OnboardingSession.user_id == user_id,
                    OnboardingSession.state == state
                )
            )
            .order_by(OnboardingSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_recent_moderation_incidents(guild_id: int, limit: int = 50) -> List[ModerationIncident]:
    """Get recent moderation incidents for a guild."""
    from sqlalchemy import select
    
    async with get_session() as session:
        result = await session.execute(
            select(ModerationIncident)
            .where(ModerationIncident.guild_id == guild_id)
            .order_by(ModerationIncident.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def cleanup_old_data(days_old: int = 90):
    """Clean up old data to keep database size manageable."""
    from sqlalchemy import delete
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)
    
    async with get_session() as session:
        # Clean up old moderation incidents
        await session.execute(
            delete(ModerationIncident).where(
                ModerationIncident.created_at < cutoff_date
            )
        )
        
        # Clean up old processed onboarding sessions
        await session.execute(
            delete(OnboardingSession).where(
                and_(
                    OnboardingSession.reviewed_at < cutoff_date,
                    OnboardingSession.state.in_(['approved', 'denied'])
                )
            )
        )
        
        # Clean up old poll votes for closed polls
        await session.execute(
            delete(PollVote).where(
                PollVote.poll_id.in_(
                    select(Poll.id).where(
                        and_(
                            Poll.closed == True,
                            Poll.created_at < cutoff_date
                        )
                    )
                )
            )
        )
        
        # Clean up old closed polls
        await session.execute(
            delete(Poll).where(
                and_(
                    Poll.closed == True,
                    Poll.created_at < cutoff_date
                )
            )
        )
        
        await session.commit()
        print(f"Cleaned up data older than {days_old} days")


# Health check function
async def check_database_health() -> bool:
    try:
        async with get_session() as session:  # AsyncSession
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
