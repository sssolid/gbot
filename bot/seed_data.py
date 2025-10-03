# File: seed_data.py
# Location: /bot/seed_data.py

"""
Seed script for initializing default data
Run this after bot setup to create sample questions and configuration
"""

import sys
from database import db
from models import Guild, Question, QuestionOption, QuestionType, Game, Configuration
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_questions(guild_id: int):
    """Seed default application questions"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found. Make sure the bot has joined the server first.")
            return False

        # Check if questions already exist
        existing = session.query(Question).filter_by(guild_id=guild.id).count()
        if existing > 0:
            logger.warning(f"Guild already has {existing} questions. Skipping seed.")
            return False

        # Question 1: Age verification
        q1 = Question(
            guild_id=guild.id,
            question_text="Are you 18 years of age or older?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=1,
            required=True,
            active=True
        )
        session.add(q1)
        session.flush()

        # Options for Q1
        opt1_yes = QuestionOption(
            question_id=q1.id,
            option_text="Yes, I am 18 or older",
            order=1,
            immediate_reject=False
        )
        opt1_no = QuestionOption(
            question_id=q1.id,
            option_text="No, I am under 18",
            order=2,
            immediate_reject=True  # Auto-flag underage applicants
        )
        session.add_all([opt1_yes, opt1_no])

        # Question 2: How did you find us
        q2 = Question(
            guild_id=guild.id,
            question_text="How did you find our server?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=2,
            required=True,
            active=True
        )
        session.add(q2)
        session.flush()

        options_q2 = [
            "Friend/Referral",
            "Discord Server List",
            "Social Media",
            "Gaming Community",
            "Search Engine",
            "Other"
        ]

        for idx, opt_text in enumerate(options_q2):
            opt = QuestionOption(
                question_id=q2.id,
                option_text=opt_text,
                order=idx + 1,
                immediate_reject=False
            )
            session.add(opt)

        # Question 3: Gaming experience
        q3 = Question(
            guild_id=guild.id,
            question_text="What games are you interested in? (Select all that apply)",
            question_type=QuestionType.MULTI_CHOICE,
            order=3,
            required=True,
            active=True
        )
        session.add(q3)
        session.flush()

        games_list = [
            "Mortal Online 2",
            "MMORPGs in general",
            "Survival Games",
            "PvP Games",
            "Sandbox Games"
        ]

        for idx, game in enumerate(games_list):
            opt = QuestionOption(
                question_id=q3.id,
                option_text=game,
                order=idx + 1,
                immediate_reject=False
            )
            session.add(opt)

        # Question 4: Tell us about yourself
        q4 = Question(
            guild_id=guild.id,
            question_text="Tell us a bit about yourself and why you want to join our community:",
            question_type=QuestionType.LONG_TEXT,
            order=4,
            required=True,
            active=True
        )
        session.add(q4)

        # Question 5: Experience level
        q5 = Question(
            guild_id=guild.id,
            question_text="What is your experience level with Mortal Online 2?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=5,
            required=False,
            active=True
        )
        session.add(q5)
        session.flush()

        exp_levels = [
            "New Player (Never played)",
            "Beginner (0-50 hours)",
            "Intermediate (50-200 hours)",
            "Advanced (200-500 hours)",
            "Veteran (500+ hours)"
        ]

        for idx, level in enumerate(exp_levels):
            opt = QuestionOption(
                question_id=q5.id,
                option_text=level,
                order=idx + 1,
                immediate_reject=False
            )
            session.add(opt)

        session.commit()
        logger.info(f"Successfully seeded {5} questions for guild {guild_id}")
        return True


def seed_games(guild_id: int):
    """Seed default games"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

        # Check if games already exist
        existing = session.query(Game).filter_by(guild_id=guild.id).count()
        if existing > 0:
            logger.warning(f"Guild already has {existing} games. Skipping seed.")
            return False

        # Add Mortal Online 2
        game = Game(
            guild_id=guild.id,
            name="Mortal Online 2",
            enabled=True
        )
        session.add(game)
        session.commit()

        logger.info(f"Successfully seeded games for guild {guild_id}")
        return True


def seed_configuration(guild_id: int):
    """Seed default configuration"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

        # Check if config already exists
        existing = session.query(Configuration).filter_by(guild_id=guild.id).first()
        if existing:
            logger.warning("Configuration already exists. Skipping seed.")
            return False

        config = Configuration(
            guild_id=guild.id,
            welcome_template="Welcome {mention} to the server! We're glad to have you here. 🎉",
            dm_fallback_enabled=True,
            auto_ban_on_flag=False,
            announcement_enabled=True
        )
        session.add(config)
        session.commit()

        logger.info(f"Successfully seeded configuration for guild {guild_id}")
        return True


def seed_all(guild_id: int):
    """Seed all default data"""
    logger.info(f"Starting seed process for guild {guild_id}")

    success = True

    if not seed_configuration(guild_id):
        success = False

    if not seed_games(guild_id):
        success = False

    if not seed_questions(guild_id):
        success = False

    if success:
        logger.info("✅ Seed process completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Use /set_channel to configure bot channels")
        logger.info("2. Use /set_role to configure role hierarchy")
        logger.info("3. Use /view_config to verify your setup")
    else:
        logger.warning("⚠️ Seed process completed with warnings. Check logs above.")

    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_data.py <guild_id>")
        print("\nExample: python seed_data.py 123456789012345678")
        print("\nTo find your guild ID:")
        print("1. Enable Developer Mode in Discord (User Settings > Advanced)")
        print("2. Right-click your server icon")
        print("3. Click 'Copy Server ID'")
        sys.exit(1)

    try:
        guild_id = int(sys.argv[1])
    except ValueError:
        print("Error: Guild ID must be a number")
        sys.exit(1)

    # Initialize database
    db.create_tables()

    # Run seed
    seed_all(guild_id)