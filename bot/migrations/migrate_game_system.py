# File: migrate_game_systems.py
# Location: /bot/migrate_game_systems.py
# Migration script to add game system tables

import sys
from database import db
from models import Base
# Import extended models
from models_game_db import (
    GameItemCategory, GameItem
)
from models_rpg import (
    UserProfile, RPGItem, InventoryItem,
    EquippedItem, Enemy, BattleLog, DailyQuest, UserQuestProgress,
    Trade, Leaderboard
)

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add new tables for game systems"""
    logger.info("Starting migration for game systems...")

    try:
        # Create all new tables
        Base.metadata.create_all(db.engine)
        logger.info("✅ Successfully created game system tables")

        # List new tables
        new_tables = [
            'game_item_categories',
            'game_items',
            'user_profiles',
            'rpg_items',
            'inventory_items',
            'equipped_items',
            'enemies',
            'battle_logs',
            'daily_quests',
            'user_quest_progress',
            'trades',
            'leaderboards'
        ]

        logger.info("\n📋 New tables created:")
        for table in new_tables:
            logger.info(f"  ✓ {table}")

        logger.info("\n🎮 Game systems migration complete!")
        logger.info("\nNext steps:")
        logger.info("1. Run: python bot/seed_game_data.py YOUR_GUILD_ID")
        logger.info("2. Add 'cogs.game_items' to bot.py initial_extensions")
        logger.info("3. Add 'cogs.rpg_game' to bot.py initial_extensions")
        logger.info("4. Restart the bot")

        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Game Systems Migration")
    logger.info("=" * 60)

    # Backup reminder
    logger.info("\n⚠️  IMPORTANT: Make sure you have a database backup!")
    response = input("Continue with migration? (yes/no): ")

    if response.lower() != 'yes':
        logger.info("Migration cancelled.")
        sys.exit(0)

    success = migrate()
    sys.exit(0 if success else 1)