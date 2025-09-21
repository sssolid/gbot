"""
Database models and setup for the Guild Management Bot
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, 
    JSON, String, Text, create_engine, select
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
    key = Column(String(255), nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    position = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OnboardingRule(Base):
    __tablename__ = 'onboarding_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    when_conditions = Column(JSON, nullable=False)  # Array of {key, value} conditions
    suggest_roles = Column(JSON, nullable=False)  # Array of role IDs or names
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OnboardingSession(Base):
    __tablename__ = 'onboarding_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False)
    state = Column(String(50), default='in_progress')  # 'in_progress', 'completed', 'approved', 'denied'
    answers = Column(JSON, default=dict)  # {question_qid: answer}
    suggestion = Column(JSON, nullable=True)  # Suggested roles from rules engine
    denial_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(BigInteger, nullable=True)


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    discord_user_id = Column(BigInteger, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    timezone = Column(String(50), nullable=True)
    flags = Column(JSON, default=dict)


class Character(Base):
    __tablename__ = 'characters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    archetype = Column(String(100), nullable=True)
    build_notes = Column(Text, nullable=True)
    is_main = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="characters")


class Poll(Base):
    __tablename__ = 'polls'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    author_id = Column(BigInteger, nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # Array of option strings
    is_anonymous = Column(Boolean, default=False)
    status = Column(String(50), default='active')  # 'active', 'closed'
    closes_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class PollVote(Base):
    __tablename__ = 'poll_votes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    option_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    poll = relationship("Poll", backref="votes")


class ModerationIncident(Base):
    __tablename__ = 'moderation_incidents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    type = Column(String(50), nullable=False)  # 'spam', 'swear', 'manual'
    reason = Column(Text, nullable=True)
    message_snapshot = Column(JSON, nullable=True)
    action_taken = Column(String(100), nullable=True)  # 'delete', 'warn', 'timeout'
    moderator_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Announcement(Base):
    __tablename__ = 'announcements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    author_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    content = Column(Text, nullable=False)
    scheduled_for = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Database connection and session management
_engine = None
_session_maker = None


async def init_database(database_url: str):
    """Initialize the database connection and create tables."""
    global _engine, _session_maker
    
    # Convert SQLite URL for async if needed
    if database_url.startswith('sqlite:///'):
        database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    
    _engine = create_async_engine(database_url, echo=False)
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    
    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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