# File: seed_advanced_data.py
# Location: /bot/seed_advanced_data.py

"""
Seed script for advanced features (shop items, dungeon rooms, recipes)
"""

import sys
import json

from config import Config
from database import db
from models import Guild
from models_rpg import RPGItem, RPGItemRarity, RPGItemSlot, ShopItem, DungeonRoom, Recipe, StructureType
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_shop_items():
    """Populate NPC shop with items"""
    with db.session_scope() as session:
        # Check if shop items exist
        existing = session.query(ShopItem).count()
        if existing > 0:
            logger.warning(f"Shop items already exist ({existing}). Skipping.")
            return False

        # Get some basic items
        items = session.query(RPGItem).limit(15).all()

        if not items:
            logger.error("No RPG items found! Run seed_game_data.py first.")
            return False

        for item in items:
            shop_item = ShopItem(
                item_id=item.id,
                buy_price=item.buy_price if item.buy_price > 0 else 100,
                stock=-1,  # Unlimited
                requires_level=item.level_required
            )
            session.add(shop_item)

        session.commit()
        logger.info(f"✅ Seeded {len(items)} shop items")
        return True


def seed_dungeon_rooms():
    """Populate dungeon room types"""
    with db.session_scope() as session:
        existing = session.query(DungeonRoom).count()
        if existing > 0:
            logger.warning(f"Dungeon rooms already exist ({existing}). Skipping.")
            return False

        rooms = [
            DungeonRoom(
                room_type='combat',
                name='Monster Den',
                description='A room filled with hostile creatures',
                visual='👹👹👹',
                encounters=json.dumps([{"enemy_id": 1, "count": 3}]),
                min_floor=1
            ),
            DungeonRoom(
                room_type='treasure',
                name='Treasure Chamber',
                description='Gold and items scattered around',
                visual='💎💰💎',
                loot_table=json.dumps([{"item_id": 1, "chance": 0.5}]),
                min_floor=1
            ),
            DungeonRoom(
                room_type='rest',
                name='Safe Haven',
                description='A peaceful room to recover',
                visual='🛏️🔥🛏️',
                min_floor=1
            ),
            DungeonRoom(
                room_type='boss',
                name='Boss Arena',
                description='A massive chamber for epic battles',
                visual='🐲👑🐲',
                encounters=json.dumps([{"enemy_id": 6, "count": 1}]),
                min_floor=5
            ),
            DungeonRoom(
                room_type='trap',
                name='Trapped Hallway',
                description='Danger lurks in every shadow',
                visual='⚠️💥⚠️',
                min_floor=2
            ),
            DungeonRoom(
                room_type='shop',
                name='Wandering Merchant',
                description='A mysterious merchant appears',
                visual='🏪💰🏪',
                min_floor=3
            )
        ]

        session.add_all(rooms)
        session.commit()
        logger.info(f"✅ Seeded {len(rooms)} dungeon room types")
        return True


def seed_recipes():
    """Populate crafting recipes"""
    with db.session_scope() as session:
        existing = session.query(Recipe).count()
        if existing > 0:
            logger.warning(f"Recipes already exist ({existing}). Skipping.")
            return False

        # Get items for recipes
        items = session.query(RPGItem).all()
        if len(items) < 5:
            logger.warning("Not enough items for recipes. Skipping.")
            return False

        recipes = [
            Recipe(
                name='Upgrade Steel Sword',
                description='Enhance a steel sword to be stronger',
                result_item_id=items[1].id if len(items) > 1 else items[0].id,
                result_quantity=1,
                ingredients=json.dumps([
                    {"item_id": items[0].id, "quantity": 1},
                    {"item_id": items[4].id if len(items) > 4 else items[0].id, "quantity": 2}
                ]),
                requires_level=5,
                gold_cost=500,
                craft_time=300
            ),
            Recipe(
                name='Craft Health Potion',
                description='Brew a healing potion',
                result_item_id=items[6].id if len(items) > 6 else items[0].id,
                result_quantity=3,
                ingredients=json.dumps([
                    {"item_id": items[0].id, "quantity": 5}
                ]),
                requires_level=1,
                gold_cost=50,
                craft_time=60
            )
        ]

        session.add_all(recipes)
        session.commit()
        logger.info(f"✅ Seeded {len(recipes)} recipes")
        return True


def seed_all(guild_id: int):
    """Seed all advanced feature data"""
    logger.info(f"Starting advanced data seed for guild {guild_id}")

    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            logger.error(f"Guild {guild_id} not found!")
            return False

    success = True

    if not seed_shop_items():
        success = False

    if not seed_dungeon_rooms():
        success = False

    if not seed_recipes():
        success = False

    if success:
        logger.info("\n✅ Advanced data seed completed successfully!")
        logger.info("\nAvailable commands:")
        logger.info("\n🏰 Raid System:")
        logger.info("  /raid_start - Start a collaborative raid (Admin)")
        logger.info("  /raid_join - Join active raid")
        logger.info("  /raid_status - View raid progress")
        logger.info("\n🏪 Shop & Market:")
        logger.info("  /shop - Browse NPC shop")
        logger.info("  /buy <id> - Purchase item")
        logger.info("  /sell <id> - Sell item")
        logger.info("  /market - Browse player marketplace")
        logger.info("  /market_list - List item for sale")
        logger.info("  /market_buy - Purchase from player")
        logger.info("\n🏠 Structures:")
        logger.info("  /structures - View your structures")
        logger.info("  /structure_build - Build new structure")
        logger.info("  /store - Store items in structure")
        logger.info("  /retrieve - Retrieve items")
        logger.info("\n🗺️ Dungeons:")
        logger.info("  /dungeon_enter - Start dungeon exploration")
        logger.info("  /dungeon_map - View current dungeon")
        logger.info("  Use navigation buttons to explore!")
    else:
        logger.warning("\n⚠️ Seed process completed with warnings")

    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_advanced_data.py <guild_id> [--dev]")
        print("\nThis will seed:")
        print("  • Shop items")
        print("  • Dungeon room types")
        print("  • Crafting recipes")
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

    seed_all(guild_id)