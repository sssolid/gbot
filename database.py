"""
Database models and setup for the Guild Management Bot - FIXED VERSION
"""
import json
from datetime import datetime, timezone
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
    rules_channel_id = Column(BigInteger, nullable=True)
    general_channel_id = Column(BigInteger, nullable=True)
    admin_dashboard_channel_id = Column(BigInteger, nullable=True)
    admin_dashboard_message_id = Column(BigInteger, nullable=True)
    member_hub_channel_id = Column(BigInteger, nullable=True)
    member_hub_message_id = Column(BigInteger, nullable=True)
    timezone_offset = Column(Integer, default=0)  # Offset in hours from UTC
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ConfigKV(Base):
    __tablename__ = 'config_kv'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    key = Column(String(255), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_key', 'guild_id', 'key'),
    )


class OnboardingQuestion(Base):
    __tablename__ = 'onboarding_questions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    qid = Column(String(100), nullable=False)  # Unique identifier for the question
    prompt = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # 'single_select', 'text', 'timezone', etc.
    required = Column(Boolean, default=True)
    options = Column(JSON, nullable=True)  # For single_select questions
    map_to = Column(String(100), nullable=True)  # FIXED: Now nullable with default
    position = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    user_timezone = Column(String(20), nullable=True)  # User's timezone
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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
    timezone = Column(String(20), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_user', 'guild_id', 'user_id'),
    )


class Character(Base):
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    race = Column(String(100), nullable=True)  # MO2 race
    archetype = Column(String(100), nullable=True)  # Main archetype
    subtype = Column(String(100), nullable=True)  # Specific build type
    professions = Column(JSON, nullable=True)  # Array of professions/skills
    build_url = Column(Text, nullable=True)  # URL to build planner
    build_notes = Column(Text, nullable=True)
    is_main = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_user_characters', 'guild_id', 'user_id'),
        Index('idx_guild_race', 'guild_id', 'race'),
        Index('idx_guild_archetype', 'guild_id', 'archetype'),
    )


class CharacterArchetype(Base):
    """Dynamic archetype/subtype definitions for easy management"""
    __tablename__ = 'character_archetypes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_archetype = Column(String(100), nullable=True)  # For subtypes
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_archetype_active', 'guild_id', 'is_active'),
    )


class Poll(Base):
    __tablename__ = 'polls'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    creator_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    options = Column(JSON, nullable=False)  # Array of option strings
    anonymous = Column(Boolean, default=False)
    multiple_choice = Column(Boolean, default=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    ends_at = Column(DateTime, nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_active_polls', 'guild_id', 'is_active'),
        Index('idx_ends_at', 'ends_at'),
    )


class PollVote(Base):
    __tablename__ = 'poll_votes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    options = Column(JSON, nullable=False)  # Array of selected option indices
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_poll_user_vote', 'poll_id', 'user_id'),
    )


class Announcement(Base):
    __tablename__ = 'announcements'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    author_id = Column(BigInteger, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    target_channel_id = Column(BigInteger, nullable=False)
    scheduled_for = Column(DateTime, nullable=True, index=True)
    mention_everyone = Column(Boolean, default=False)
    message_id = Column(BigInteger, nullable=True)
    is_sent = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_guild_scheduled', 'guild_id', 'scheduled_for'),
        Index('idx_unsent_announcements', 'is_sent', 'scheduled_for'),
    )


class ModerationIncident(Base):
    __tablename__ = 'moderation_incidents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    moderator_id = Column(BigInteger, nullable=True)
    type = Column(String(50), nullable=False)  # 'spam', 'swear', 'manual', etc.
    action = Column(String(50), nullable=False)  # 'delete', 'warn', 'timeout', etc.
    reason = Column(Text, nullable=True)
    message_content = Column(Text, nullable=True)  # For audit purposes
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index('idx_guild_incidents', 'guild_id', 'created_at'),
        Index('idx_user_incidents', 'user_id', 'created_at'),
    )


class MessageLog(Base):
    """Enhanced message logging for audit purposes"""
    __tablename__ = 'message_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    content = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)  # URLs and metadata
    embeds = Column(JSON, nullable=True)  # Embed data
    action = Column(String(20), nullable=False)  # 'created', 'edited', 'deleted'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index('idx_guild_channel_logs', 'guild_id', 'channel_id'),
        Index('idx_message_action_logs', 'message_id', 'action'),
        Index('idx_user_logs', 'user_id', 'created_at'),
    )


# Database setup
_engine = None
_session_maker = None


async def init_database(database_url: str = "sqlite+aiosqlite:///guild_bot.sqlite"):
    """Initialize the database connection and create tables."""
    global _engine, _session_maker

    # Fix timezone handling in SQLite
    if "sqlite" in database_url:
        _engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )
    else:
        _engine = create_async_engine(database_url, echo=False)

    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)

    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Database initialized: {database_url}")


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
            config.updated_at = datetime.now(timezone.utc)

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
    from sqlalchemy import select, and_

    async with get_session() as session:
        result = await session.execute(
            select(ModerationIncident)
            .where(ModerationIncident.guild_id == guild_id)
            .order_by(ModerationIncident.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def log_message_action(guild_id: int, channel_id: int, message_id: int,
                           user_id: int, content: str, action: str,
                           attachments: List = None, embeds: List = None):
    """Log a message action for audit purposes."""
    async with get_session() as session:
        log_entry = MessageLog(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            user_id=user_id,
            content=content,
            attachments=attachments,
            embeds=embeds,
            action=action
        )
        session.add(log_entry)
        await session.commit()


async def get_character_statistics(guild_id: int) -> Dict[str, Any]:
    """Get character statistics for the guild."""
    from sqlalchemy import select, func, and_

    async with get_session() as session:
        # Total characters
        total_result = await session.execute(
            select(func.count(Character.id))
            .where(Character.guild_id == guild_id)
        )
        total_characters = total_result.scalar()

        # Characters by race
        race_result = await session.execute(
            select(Character.race, func.count(Character.id))
            .where(
                and_(
                    Character.guild_id == guild_id,
                    Character.race.isnot(None)
                )
            )
            .group_by(Character.race)
        )
        race_stats = dict(race_result.all())

        # Characters by archetype
        archetype_result = await session.execute(
            select(Character.archetype, func.count(Character.id))
            .where(
                and_(
                    Character.guild_id == guild_id,
                    Character.archetype.isnot(None)
                )
            )
            .group_by(Character.archetype)
        )
        archetype_stats = dict(archetype_result.all())

        # Main characters
        main_result = await session.execute(
            select(func.count(Character.id))
            .where(
                and_(
                    Character.guild_id == guild_id,
                    Character.is_main == True
                )
            )
        )
        main_characters = main_result.scalar()

        return {
            "total_characters": total_characters,
            "main_characters": main_characters,
            "race_distribution": race_stats,
            "archetype_distribution": archetype_stats
        }