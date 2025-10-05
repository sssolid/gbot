# File: seed_data.py
# Location: /bot/seed_data.py

"""
Seed script for initializing default data
Run this after bot setup to create sample questions and configuration
"""

import sys
from database import db
from models import Guild, Question, QuestionOption, QuestionType, Game, Configuration, ChannelRegistry, RoleRegistry, RoleTier
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_questions(guild_id: int):
    """Seed default application questions with conditional follow-ups"""
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

        order = 0

        # Age verification
        order += 1
        av = Question(
            guild_id=guild.id,
            question_text="Are you 18 years of age or older?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=True,
            active=True
        )
        session.add(av)
        session.flush()

        av_yes = QuestionOption(
            question_id=av.id,
            option_text="Yes, I am 18 or older",
            order=1,
            immediate_reject=False
        )
        av_no = QuestionOption(
            question_id=av.id,
            option_text="No, I am under 18",
            order=2,
            immediate_reject=True
        )
        session.add_all([av_yes, av_no])

        # How did you find us? (with conditional follow-up)
        order += 1
        fu = Question(
            guild_id=guild.id,
            question_text="How did you find our server?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=True,
            active=True
        )
        session.add(fu)
        session.flush()

        fu_friend = QuestionOption(
            question_id=fu.id,
            option_text="Friend/Referral",
            order=1,
            immediate_reject=False
        )
        fu_discord = QuestionOption(
            question_id=fu.id,
            option_text="Discord Server List",
            order=2,
            immediate_reject=False
        )
        fu_social = QuestionOption(
            question_id=fu.id,
            option_text="Social Media",
            order=3,
            immediate_reject=False
        )
        fu_gaming = QuestionOption(
            question_id=fu.id,
            option_text="Gaming Community",
            order=4,
            immediate_reject=False
        )
        fu_search = QuestionOption(
            question_id=fu.id,
            option_text="Search Engine",
            order=5,
            immediate_reject=False
        )
        fu_other = QuestionOption(
            question_id=fu.id,
            option_text="Other",
            order=6,
            immediate_reject=False
        )
        session.add_all([fu_friend, fu_discord, fu_social, fu_gaming, fu_search, fu_other])
        session.flush()

        # Conditional question: If they selected "Friend/Referral"
        order += 1
        fu_followup = Question(
            guild_id=guild.id,
            question_text="Who referred you? Please provide their username so we can verify.",
            question_type=QuestionType.SHORT_TEXT,
            order=order,
            required=True,
            active=True,
            parent_question_id=fu.id,
            parent_option_id=fu_friend.id
        )
        session.add(fu_followup)

        # Conditional question: If they selected "Other"
        order += 1
        fu_other_followup = Question(
            guild_id=guild.id,
            question_text="Please tell us how you found us:",
            question_type=QuestionType.SHORT_TEXT,
            order=order,
            required=True,
            active=True,
            parent_question_id=fu.id,
            parent_option_id=fu_other.id
        )
        session.add(fu_other_followup)

        # Family first question
        order += 1
        fq = Question(
            guild_id=guild.id,
            question_text="Most of us are parents who value traditional family roles. Do you have kids or support family first priorities?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=False,
            active=True
        )
        session.add(fq)
        session.flush()

        fq_yes = QuestionOption(
            question_id=fq.id,
            option_text="Yes, I have kids or support family first priorities.",
            order=1,
            immediate_reject=False
        )
        fq_no = QuestionOption(
            question_id=fq.id,
            option_text="No, I do not have kids or support family first priorities.",
            order=2,
            immediate_reject=True
        )
        session.add_all([fq_yes, fq_no])

        # Personal Responsibility
        order += 1
        pr = Question(
            guild_id=guild.id,
            question_text="We place a strong emphasis on personal responsibility and traditional values. Do these principles align with your own?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=False,
            active=True
        )
        session.add(pr)
        session.flush()

        pr_responses = [
            {"q": "Yes, I strongly share these views.", "rj": False},
            {"q": "I mostly agree with these views.", "rj": False},
            {"q": "I respect them, though I hold different priorities.", "rj": True},
            {"q": "No, I do not share these views.", "rj": True}
        ]

        for idx, question in enumerate(pr_responses):
            opt = QuestionOption(
                question_id=pr.id,
                option_text=question.get("q"),
                order=idx + 1,
                immediate_reject=question.get("rj")
            )
            session.add(opt)

        # Pronouns
        order += 1
        pro = Question(
            guild_id=guild.id,
            question_text="We don't do pronouns here. You're addressed by your username or standard he/she based on what's obvious. Will you push others to use them?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=False,
            active=True
        )
        session.add(pro)
        session.flush()

        pro_yes = QuestionOption(
            question_id=pro.id,
            option_text="Yes, I want to be addressed appropriately.",
            order=1,
            immediate_reject=True
        )
        pro_no = QuestionOption(
            question_id=pro.id,
            option_text="No, I agree with this policy.",
            order=2,
            immediate_reject=False
        )
        session.add_all([pro_yes, pro_no])

        # Adults
        order += 1
        adult = Question(
            guild_id=guild.id,
            question_text="Our guild has thick skin. Banter and trash talk are part of gaming. If someone says something you don't like, how will you respond?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=False,
            active=True
        )
        session.add(adult)
        session.flush()

        adult_responses = [
            {"q": "I will not be disrespected.", "rj": True},
            {"q": "I will ignore it.", "rj": False},
            {"q": "I will inform an officer.", "rj": True}
        ]

        for idx, question in enumerate(adult_responses):
            opt = QuestionOption(
                question_id=adult.id,
                option_text=question.get("q"),
                order=idx + 1,
                immediate_reject=question.get("rj")
            )
            session.add(opt)

        # Agree to terms
        order += 1
        agree = Question(
            guild_id=guild.id,
            question_text="This guild is for conservative, family focused gamers who can handle adult humor and zero drama. If you're not 100% on board with our values, you'll be a problem. Are you in?",
            question_type=QuestionType.SINGLE_CHOICE,
            order=order,
            required=True,
            active=True
        )
        session.add(agree)
        session.flush()

        agree_yes = QuestionOption(
            question_id=agree.id,
            option_text="Yes, this guild seems like a good fit for me.",
            order=1,
            immediate_reject=False
        )
        agree_no = QuestionOption(
            question_id=agree.id,
            option_text="No, I don't believe this guild is for me.",
            order=2,
            immediate_reject=True
        )
        session.add_all([agree_yes, agree_no])

        # Gaming Experience
        order += 1
        ge = Question(
            guild_id=guild.id,
            question_text="What games are you interested in? (Select all that apply)",
            question_type=QuestionType.MULTI_CHOICE,
            order=order,
            required=True,
            active=True
        )
        session.add(ge)
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
                question_id=ge.id,
                option_text=game,
                order=idx + 1,
                immediate_reject=False
            )
            session.add(opt)

        # Tell us about yourself
        order += 1
        about = Question(
            guild_id=guild.id,
            question_text="Tell us a bit about yourself and why you want to join our community:",
            question_type=QuestionType.LONG_TEXT,
            order=order,
            required=False,
            active=True
        )
        session.add(about)

        session.commit()
        logger.info(f"Successfully seeded questions for guild {guild_id}")
        return True


def seed_games(guild_id: int):
    """Seed default games"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

        existing = session.query(Game).filter_by(guild_id=guild.id).count()
        if existing > 0:
            logger.warning(f"Guild already has {existing} games. Skipping seed.")
            return False

        game = Game(
            guild_id=guild.id,
            name="Mortal Online 2",
            enabled=True
        )
        session.add(game)
        session.commit()

        logger.info(f"Successfully seeded games for guild {guild_id}")
        return True


def seed_channels(guild_id: int):
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

        existing = session.query(ChannelRegistry).filter_by(guild_id=guild.id).count()
        if existing > 0:
            logger.warning(f"Guild already has {existing} channels. Skipping seed.")
            return False

        channel = ChannelRegistry(
            guild_id=guild.id,
            channel_type="announcements",
            channel_id=1418810985266942083
        )
        session.add(channel)
        channel = ChannelRegistry(
            guild_id=guild.id,
            channel_type="moderator_queue",
            channel_id=1419154339536044084
        )
        session.add(channel)
        channel = ChannelRegistry(
            guild_id=guild.id,
            channel_type="welcome",
            channel_id=1418809469202337933
        )
        session.add(channel)
        session.commit()

        logger.info(f"Successfully seeded channels for guild {guild_id}")
        return True


def seed_roles(guild_id: int):
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

        existing = session.query(RoleRegistry).filter_by(guild_id=guild.id).count()
        if existing > 0:
            logger.warning(f"Guild already has {existing} roles. Skipping seed.")
            return False

        role = RoleRegistry(
            guild_id=guild.id,
            role_tier="SOVEREIGN",
            role_id=1418955168204066937,
            hierarchy_level=3
        )
        session.add(role)
        role = RoleRegistry(
            guild_id=guild.id,
            role_tier="TEMPLAR",
            role_id=1418955465697660939,
            hierarchy_level=2
        )
        session.add(role)
        role = RoleRegistry(
            guild_id=guild.id,
            role_tier="KNIGHT",
            role_id=1418955679690920039,
            hierarchy_level=1
        )
        session.add(role)
        role = RoleRegistry(
            guild_id=guild.id,
            role_tier="SQUIRE",
            role_id=1418955825510219887,
            hierarchy_level=1
        )
        session.add(role)
        role = RoleRegistry(
            guild_id=guild.id,
            role_tier="APPLICANT",
            role_id=1423764072062783488,
            hierarchy_level=0
        )
        session.add(role)

        session.commit()

        logger.info(f"Successfully seeded roles for guild {guild_id}")
        return True


def seed_configuration(guild_id: int):
    """Seed default configuration"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()

        if not guild:
            logger.error(f"Guild {guild_id} not found.")
            return False

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

    if not seed_channels(guild_id):
        return False

    if not seed_roles(guild_id):
        return False

    if success:
        logger.info("✅ Seed process completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Use /set_channel to configure bot channels (announcements, moderator_queue, welcome, rules)")
        logger.info("2. Use /set_role to configure role hierarchy (sovereign, templar, knight, squire, applicant)")
        logger.info("3. Use /set_welcome_message to set the welcome channel message")
        logger.info("4. Use /set_rules_message to set the rules channel message")
        logger.info("5. Use /view_config to verify your setup")
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