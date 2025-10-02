"""
Database models and setup for the Guild Management Bot - FIXED VERSION
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer,
    JSON, String, Text, Index
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

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


class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    main_character_id = Column(Integer, nullable=True)
    timezone = Column(String(50), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    roles = Column(JSON, default=list)  # Array of role IDs
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_user', 'guild_id', 'id'),
    )


class Character(Base):
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    archetype = Column(String(100), nullable=True)
    build_notes = Column(Text, nullable=True)
    is_main = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_user_character', 'guild_id', 'user_id'),
        Index('idx_user_main_character', 'user_id', 'is_main'),
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
    user_timezone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index('idx_guild_user_session', 'guild_id', 'user_id'),
        Index('idx_state', 'state'),
    )


class Poll(Base):
    __tablename__ = 'polls'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=True, index=True)
    author_id = Column(BigInteger, nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # Array of option strings
    is_anonymous = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    status = Column(String(20), default='active', index=True)  # FIXED: Added status field
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ends_at = Column(DateTime, nullable=True, index=True)

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
    action_taken = Column(String(50), nullable=True)  # FIXED: Added action_taken field
    message_id = Column(BigInteger, nullable=True)
    channel_id = Column(BigInteger, nullable=True)
    reason = Column(Text, nullable=True)
    content_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_user_incidents', 'guild_id', 'user_id'),
        Index('idx_guild_type_incidents', 'guild_id', 'type'),
    )


# FIXED: Added missing ModerationLog class
class ModerationLog(Base):
    __tablename__ = 'moderation_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    moderator_id = Column(BigInteger, nullable=False)
    target_user_id = Column(BigInteger, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # 'warn', 'timeout', 'ban', etc.
    reason = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in minutes for timeouts
    message_snapshot = Column(JSON, nullable=True)  # Original message data if applicable
    action_taken = Column(String(100), nullable=True)  # Description of action taken
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_guild_target', 'guild_id', 'target_user_id'),
        Index('idx_guild_moderator', 'guild_id', 'moderator_id'),
        Index('idx_action_type', 'action_type'),
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


# Database connection setup
engine = None
async_session: Optional[async_sessionmaker[AsyncSession]] = None


async def setup_database(database_url: str = "sqlite+aiosqlite:///guild_bot.sqlite"):
    """Initialize the database connection and create tables."""
    global engine, async_session

    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> AsyncSession:
    """Get a database session."""
    if async_session is None:
        raise RuntimeError("Database not initialized. Call setup_database() first.")
    return async_session()


async def close_database():
    """Close database connections."""
    global engine
    if engine:
        await engine.dispose()


# Utility functions for common queries
async def get_guild_config(guild_id: int) -> Optional[GuildConfig]:
    """Get guild configuration."""
    async with get_session() as session:
        result = await session.get(GuildConfig, guild_id)
        return result


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