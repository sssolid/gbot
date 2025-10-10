# File: migrate_advanced_features.py
# Location: /bot/migrate_advanced_features.py
# Migration for raids, shop, structures, and dungeons

import sys
from database import db
from models import Base
from models_rpg import (
    # Raids
    Raid, RaidWave, RaidParticipant, RaidLoot, LootRoll,
    # Shop
    ShopItem, PlayerMarketListing, TransactionLog,
    # Structures
    PlayerStructure, StructureStorage,
    # Dungeons
    DungeonRun, DungeonRoom, DungeonLoot,
    # Crafting
    Recipe, CraftingQueue
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_inventory_columns():
    """Add inventory capacity columns to user_profiles"""
    from sqlalchemy import text

    try:
        with db.engine.connect() as conn:
            # Check if columns exist
            result = conn.execute(text("""
                                       SELECT column_name
                                       FROM information_schema.columns
                                       WHERE table_name = 'user_profiles'
                                         AND column_name IN ('max_inventory_slots', 'current_inventory_slots')
                                       """))

            existing = [row[0] for row in result]

            if 'max_inventory_slots' not in existing:
                conn.execute(text("""
                                  ALTER TABLE user_profiles
                                      ADD COLUMN max_inventory_slots INTEGER DEFAULT 20
                                  """))
                conn.commit()
                logger.info("✓ Added max_inventory_slots column")

            if 'current_inventory_slots' not in existing:
                conn.execute(text("""
                                  ALTER TABLE user_profiles
                                      ADD COLUMN current_inventory_slots INTEGER DEFAULT 0
                                  """))
                conn.commit()
                logger.info("✓ Added current_inventory_slots column")

    except Exception as e:
        logger.error(f"Error adding columns: {e}")


def migrate():
    """Add new tables for advanced features"""
    logger.info("Starting migration for advanced features...")

    try:
        # Add columns first
        add_inventory_columns()

        # Create all new tables
        Base.metadata.create_all(db.engine)
        logger.info("✅ Successfully created advanced feature tables")

        # List new tables
        new_tables = [
            # Raids
            'raids',
            'raid_waves',
            'raid_participants',
            'raid_loot',
            'loot_rolls',
            # Shop
            'shop_items',
            'player_market_listings',
            'transaction_logs',
            # Structures
            'player_structures',
            'structure_storage',
            # Dungeons
            'dungeon_runs',
            'dungeon_rooms',
            'dungeon_loot',
            # Crafting
            'recipes',
            'crafting_queue'
        ]

        logger.info("\n📋 New tables created:")
        for table in new_tables:
            logger.info(f"  ✓ {table}")

        logger.info("\n🎮 Advanced features migration complete!")
        logger.info("\nFeatures added:")
        logger.info("  🏰 Collaborative Raid System")
        logger.info("  🏪 Shop & Marketplace")
        logger.info("  🏠 Player Structures")
        logger.info("  🗺️ Roguelike Dungeons")
        logger.info("  🛠️ Crafting System")

        logger.info("\nNext steps:")
        logger.info("1. Run: python bot/seed_advanced_data.py YOUR_GUILD_ID")
        logger.info("2. Add new cogs to bot.py:")
        logger.info("   - 'cogs.raids'")
        logger.info("   - 'cogs.shop'")
        logger.info("   - 'cogs.structures'")
        logger.info("   - 'cogs.dungeon'")
        logger.info("3. Restart the bot")

        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Advanced Features Migration")
    logger.info("=" * 60)

    # Backup reminder
    logger.info("\n⚠️  IMPORTANT: Make sure you have a database backup!")
    response = input("Continue with migration? (yes/no): ")

    if response.lower() != 'yes':
        logger.info("Migration cancelled.")
        sys.exit(0)

    success = migrate()
    sys.exit(0 if success else 1)