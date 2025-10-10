# File: seed_data.py
# Location: /bot/seed_data.py

"""
Seed script for initializing default data
Run this after bot setup to create sample questions and configuration
"""
import json
import sys

from config import Config
from database import db
from models import Guild, Question, QuestionOption, QuestionType, Game, Configuration, ChannelRegistry, RoleRegistry, RoleTier
import logging

from seed_data import seed_all as seed_configuration
from seed_game_data import seed_all as seed_all_rpg
from seed_advanced_data import seed_all as seed_all_advanced

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_all(guild_id: int, config: Config):
    """Seed all default data"""
    logger.info(f"Starting seed process for guild {guild_id}")

    success = True

    # Initialize config and database
    dev_mode = "--dev" in sys.argv
    config = Config(dev=dev_mode)
    db.init_app(config)

    if not seed_configuration(guild_id, dev_mode=dev_mode):
        success = False

    if not seed_all_rpg(guild_id):
        success = False

    if not seed_all_advanced(guild_id):
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
        print("Usage: python seed_data.py <guild_id> [--dev]")
        print("\nExample: python seed_data.py 123456789012345678 --dev")
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

    # Initialize config and database
    dev_mode = "--dev" in sys.argv
    config = Config(dev=dev_mode)
    db.init_app(config)

    # Initialize database
    db.create_tables()

    # Run seed
    seed_all(guild_id, config)