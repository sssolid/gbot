# File: models.py
# Location: /bot/models.py

from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime, Text,
    ForeignKey, Table, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from datetime import datetime
import enum

Base = declarative_base()


# Enums
class ApplicationStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    IN_PROGRESS = "in_progress"


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


class ActionType(enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    BAN = "ban"
    UNBAN = "unban"


# Association tables
submission_answers = Table(
    'submission_answers',
    Base.metadata,
    Column('submission_id', Integer, ForeignKey('submissions.id')),
    Column('answer_id', Integer, ForeignKey('answers.id'))
)


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


class ChannelRegistry(Base):
    __tablename__ = 'channel_registry'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    channel_type = Column(String(50), nullable=False)  # announcements, moderator_queue, etc.
    channel_id = Column(BigInteger, nullable=False)

    guild = relationship('Guild', back_populates='channels')


class RoleRegistry(Base):
    __tablename__ = 'role_registry'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    role_tier = Column(SQLEnum(RoleTier), nullable=False)
    role_id = Column(BigInteger, nullable=False)
    hierarchy_level = Column(Integer, default=0)  # Higher = more permissions

    guild = relationship('Guild', back_populates='roles')


class Member(Base):
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100))
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
    blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(Text)
    joined_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)

    guild = relationship('Guild', back_populates='members')
    submissions = relationship('Submission', back_populates='member', cascade='all, delete-orphan')
    characters = relationship('Character', back_populates='member', cascade='all, delete-orphan')


class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    order = Column(Integer, nullable=False)
    required = Column(Boolean, default=True)
    active = Column(Boolean, default=True)

    # Conditional logic hooks
    parent_question_id = Column(Integer, ForeignKey('questions.id'), nullable=True)
    parent_option_id   = Column(Integer, ForeignKey('question_options.id'), nullable=True)

    # --- Relationships ---
    guild = relationship('Guild', back_populates='questions')

    # EXPLICIT foreign_keys to disambiguate the path to QuestionOption
    options = relationship(
        'QuestionOption',
        back_populates='question',
        cascade='all, delete-orphan',
        single_parent=True,
        foreign_keys=lambda: [QuestionOption.question_id],
        primaryjoin=lambda: Question.id == QuestionOption.question_id,
    )

    # Answers unchanged (assuming Answer.question_id → questions.id)
    answers = relationship('Answer', back_populates='question', cascade='all, delete-orphan')

    # Self-referential parent (explicit foreign_keys)
    parent_question = relationship(
        'Question',
        remote_side=lambda: [Question.id],
        foreign_keys=lambda: [Question.parent_question_id],
        backref=backref('conditional_questions', cascade='all, delete-orphan'),
    )

    # Optional: direct handle to the parent option for convenience
    parent_option = relationship(
        'QuestionOption',
        foreign_keys=lambda: [Question.parent_option_id],
        viewonly=True,  # flip to False only if you intend to assign through it
    )


class QuestionOption(Base):
    __tablename__ = 'question_options'

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    option_text = Column(String(255), nullable=False)
    order = Column(Integer, nullable=False)
    immediate_reject = Column(Boolean, default=False)

    # EXPLICIT foreign_keys to disambiguate the path back to Question
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
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.IN_PROGRESS)
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
    roles = Column(Text)  # JSON string for multiple roles
    professions = Column(Text)  # JSON string for multiple professions
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship('Member', back_populates='characters')
    game = relationship('Game', back_populates='characters')


class ModeratorAction(Base):
    __tablename__ = 'moderator_actions'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    action_type = Column(SQLEnum(ActionType), nullable=False)
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

    guild = relationship('Guild', back_populates='config')