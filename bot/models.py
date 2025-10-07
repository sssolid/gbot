# File: models.py
# Location: /bot/models.py

from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime, Text,
    ForeignKey, Table
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.types import TypeDecorator, String
from datetime import datetime
import enum

Base = declarative_base()


class EnumAsString(TypeDecorator):
    impl = String(50)

    def __init__(self, enumtype, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enumtype = enumtype

    def process_bind_param(self, value, dialect):
        # When saving to DB
        if isinstance(value, self._enumtype):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        # When loading from DB
        if value is not None:
            return self._enumtype(value)
        return value


# Enums
class ApplicationStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"
    IN_PROGRESS = "IN_PROGRESS"


class SubmissionType(enum.Enum):
    APPLICANT = "applicant"
    FRIEND = "friend"
    REGULAR = "regular"


class QuestionType(enum.Enum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMERIC = "numeric"


class RoleTier(enum.Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"
    APPLICANT = "applicant"
    SOVEREIGN = "sovereign"
    TEMPLAR = "templar"
    KNIGHT = "knight"
    SQUIRE = "squire"
    ALLY = "ally"


class ActionType(enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    BAN = "ban"
    UNBAN = "unban"
    KICK = "kick"
    TIMEOUT = "timeout"
    PROMOTE = "promote"
    DEMOTE = "demote"
    RESET = "reset"
    STRIP_ROLES = "strip_roles"


class AppealStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProfileChangeType(enum.Enum):
    AVATAR = "avatar"
    NAME = "name"
    NICKNAME = "nickname"
    BANNER = "banner"


# Models
class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    channels = relationship('ChannelRegistry', back_populates='guild', cascade='all, delete-orphan')
    roles = relationship('RoleRegistry', back_populates='guild', cascade='all, delete-orphan')
    members = relationship('Member', back_populates='guild', cascade='all, delete-orphan')
    questions = relationship('Question', back_populates='guild', cascade='all, delete-orphan')
    games = relationship('Game', back_populates='guild', cascade='all, delete-orphan')
    config = relationship('Configuration', back_populates='guild', uselist=False, cascade='all, delete-orphan')
    message_logs = relationship('MessageLog', back_populates='guild', cascade='all, delete-orphan')
    profile_changes = relationship('ProfileChangeLog', back_populates='guild', cascade='all, delete-orphan')


class ChannelRegistry(Base):
    __tablename__ = 'channel_registry'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    channel_type = Column(String(50), nullable=False)
    channel_id = Column(BigInteger, nullable=False)

    guild = relationship('Guild', back_populates='channels')


class RoleRegistry(Base):
    __tablename__ = 'role_registry'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    role_tier = Column(EnumAsString(RoleTier), nullable=False)
    # role_tier = Column(SQLEnum(RoleTier), nullable=False)
    role_id = Column(BigInteger, nullable=False)
    hierarchy_level = Column(Integer, default=0)

    guild = relationship('Guild', back_populates='roles')


class Member(Base):
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100))
    status = Column(EnumAsString(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
    # status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
    role_tier = Column(EnumAsString(RoleTier), nullable=False)
    # role_tier = Column(SQLEnum(RoleTier), nullable=True)
    blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(Text)
    joined_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    appeal_count = Column(Integer, default=0)

    # Profile tracking
    last_avatar_url = Column(Text)
    last_display_name = Column(String(100))
    last_nickname = Column(String(100))

    guild = relationship('Guild', back_populates='members')
    submissions = relationship('Submission', back_populates='member', cascade='all, delete-orphan')
    characters = relationship('Character', back_populates='member', cascade='all, delete-orphan')
    appeals = relationship('Appeal', back_populates='member', cascade='all, delete-orphan')


class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(EnumAsString(QuestionType), nullable=False)
    # question_type = Column(SQLEnum(QuestionType), nullable=False)
    order = Column(Integer, nullable=False)
    required = Column(Boolean, default=True)
    active = Column(Boolean, default=True)

    parent_question_id = Column(Integer, ForeignKey('questions.id'), nullable=True)
    parent_option_id = Column(Integer, ForeignKey('question_options.id'), nullable=True)

    guild = relationship('Guild', back_populates='questions')
    options = relationship(
        'QuestionOption',
        back_populates='question',
        cascade='all, delete-orphan',
        single_parent=True,
        foreign_keys=lambda: [QuestionOption.question_id],
        primaryjoin=lambda: Question.id == QuestionOption.question_id,
    )
    answers = relationship('Answer', back_populates='question', cascade='all, delete-orphan')
    parent_question = relationship(
        'Question',
        remote_side=lambda: [Question.id],
        foreign_keys=lambda: [Question.parent_question_id],
        backref=backref('conditional_questions', cascade='all, delete-orphan'),
    )
    parent_option = relationship(
        'QuestionOption',
        foreign_keys=lambda: [Question.parent_option_id],
        viewonly=True,
    )


class QuestionOption(Base):
    __tablename__ = 'question_options'

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    option_text = Column(String(255), nullable=False)
    order = Column(Integer, nullable=False)
    immediate_reject = Column(Boolean, default=False)

    question = relationship(
        'Question',
        back_populates='options',
        foreign_keys=lambda: [QuestionOption.question_id],
        primaryjoin=lambda: QuestionOption.question_id == Question.id,
    )


class Submission(Base):
    __tablename__ = 'submissions'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False)
    submission_type = Column(EnumAsString(SubmissionType), default=SubmissionType.APPLICANT)
    # submission_type = Column(SQLEnum(SubmissionType), default=SubmissionType.APPLICANT)
    friend_info = Column(Text, nullable=True)
    status = Column(EnumAsString(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
    # status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
    submitted_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    reviewer_id = Column(BigInteger)
    rejection_reason = Column(Text)
    flagged = Column(Boolean, default=False)
    flag_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    member = relationship('Member', back_populates='submissions')
    answers = relationship('Answer', back_populates='submission', cascade='all, delete-orphan')
    actions = relationship('ModeratorAction', back_populates='submission', cascade='all, delete-orphan')


class Answer(Base):
    __tablename__ = 'answers'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    text_answer = Column(Text)
    numeric_answer = Column(Integer)

    submission = relationship('Submission', back_populates='answers')
    question = relationship('Question', back_populates='answers')
    selected_options = relationship('QuestionOption', secondary='answer_options')


# Association table for answer options
answer_options = Table(
    'answer_options',
    Base.metadata,
    Column('answer_id', Integer, ForeignKey('answers.id')),
    Column('option_id', Integer, ForeignKey('question_options.id'))
)


class Appeal(Base):
    __tablename__ = 'appeals'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(EnumAsString(AppealStatus), default=AppealStatus.PENDING)
    # status = Column(SQLEnum(AppealStatus), default=AppealStatus.PENDING)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    reviewer_id = Column(BigInteger)
    reviewer_note = Column(Text)

    member = relationship('Member', back_populates='appeals')


class Game(Base):
    __tablename__ = 'games'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)

    guild = relationship('Guild', back_populates='games')
    characters = relationship('Character', back_populates='game', cascade='all, delete-orphan')


class Character(Base):
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    name = Column(String(100), nullable=False)
    race = Column(String(50))
    roles = Column(Text)
    professions = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship('Member', back_populates='characters')
    game = relationship('Game', back_populates='characters')


class ModeratorAction(Base):
    __tablename__ = 'moderator_actions'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=True)
    target_user_id = Column(BigInteger, nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    action_type = Column(EnumAsString(ActionType), nullable=False)
    # action_type = Column(SQLEnum(ActionType), nullable=False)
    reason = Column(Text)
    banned = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    submission = relationship('Submission', back_populates='actions')


class Configuration(Base):
    __tablename__ = 'configurations'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False, unique=True)
    welcome_template = Column(Text, default="Welcome {mention} to the server!")
    dm_fallback_enabled = Column(Boolean, default=True)
    auto_ban_on_flag = Column(Boolean, default=False)
    announcement_enabled = Column(Boolean, default=True)

    # Logging settings
    message_logging_enabled = Column(Boolean, default=True)
    profile_change_alerts_enabled = Column(Boolean, default=True)

    # Bot-managed messages
    welcome_message_content = Column(Text, nullable=True)
    welcome_message_media_url = Column(Text, nullable=True)
    welcome_message_id = Column(BigInteger, nullable=True)

    rules_message_content = Column(Text, nullable=True)
    rules_message_media_url = Column(Text, nullable=True)
    rules_message_id = Column(BigInteger, nullable=True)

    guild = relationship('Guild', back_populates='config')


class MessageLog(Base):
    __tablename__ = 'message_logs'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100))
    content = Column(Text)
    attachments = Column(Text)  # JSON array of attachment URLs
    embeds = Column(Text)  # JSON array of embed data
    deleted = Column(Boolean, default=False)
    edited = Column(Boolean, default=False)
    original_content = Column(Text)  # For tracking edits
    timestamp = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime)
    edited_at = Column(DateTime)

    guild = relationship('Guild', back_populates='message_logs')


class ProfileChangeLog(Base):
    __tablename__ = 'profile_change_logs'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    change_type = Column(EnumAsString(ProfileChangeType), nullable=False)
    # change_type = Column(SQLEnum(ProfileChangeType), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)

    guild = relationship('Guild', back_populates='profile_changes')


class RateLimitLog(Base):
    __tablename__ = 'rate_limit_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    command = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)