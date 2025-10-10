# File: seed_game_data.py
# Location: /bot/seed_game_data.py

"""
Seed script for game data (RPG items, enemies, MO2 items)
Run after migrate_game_systems.py
"""

import sys
import json

from config import Config
from database import db
from models import Guild, Game
from models_game_db import (
    GameItem, GameItemCategory, ItemType
)
from models_rpg import (
    RPGItem, Enemy, DailyQuest, RPGItemSlot, RPGItemRarity,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_rpg_items():
    """Seed RPG mini-game items"""
    with db.session_scope() as session:
        # Check if items exist
        existing = session.query(RPGItem).count()
        if existing > 0:
            logger.warning(f"RPG items already exist ({existing}). Skipping.")
            return False

        items = [
            # Weapons
            RPGItem(
                name="Rusty Sword",
                description="A basic sword, better than nothing",
                rarity=RPGItemRarity.COMMON,
                slot=RPGItemSlot.WEAPON,
                attack_bonus=5,
                buy_price=50,
                sell_price=10,
                level_required=1,
                emoji="🗡️"
            ),
            RPGItem(
                name="Steel Sword",
                description="A reliable steel blade",
                rarity=RPGItemRarity.UNCOMMON,
                slot=RPGItemSlot.WEAPON,
                attack_bonus=12,
                buy_price=200,
                sell_price=50,
                level_required=5,
                emoji="⚔️"
            ),
            RPGItem(
                name="Dragon Slayer",
                description="Forged from dragonbone, legendary weapon",
                rarity=RPGItemRarity.LEGENDARY,
                slot=RPGItemSlot.WEAPON,
                attack_bonus=50,
                buy_price=5000,
                sell_price=1000,
                level_required=20,
                emoji="🐉"
            ),

            # Armor
            RPGItem(
                name="Leather Armor",
                description="Basic leather protection",
                rarity=RPGItemRarity.COMMON,
                slot=RPGItemSlot.CHEST,
                defense_bonus=3,
                health_bonus=10,
                buy_price=40,
                sell_price=8,
                level_required=1,
                emoji="🥼"
            ),
            RPGItem(
                name="Steel Plate",
                description="Heavy steel armor",
                rarity=RPGItemRarity.RARE,
                slot=RPGItemSlot.CHEST,
                defense_bonus=15,
                health_bonus=30,
                buy_price=500,
                sell_price=100,
                level_required=10,
                emoji="🛡️"
            ),

            # Helmets
            RPGItem(
                name="Iron Helmet",
                description="Basic head protection",
                rarity=RPGItemRarity.UNCOMMON,
                slot=RPGItemSlot.HEAD,
                defense_bonus=5,
                health_bonus=5,
                buy_price=100,
                sell_price=20,
                level_required=3,
                emoji="⛑️"
            ),

            # Consumables
            RPGItem(
                name="Health Potion",
                description="Restores 50 HP",
                rarity=RPGItemRarity.COMMON,
                slot=RPGItemSlot.CONSUMABLE,
                health_restore=50,
                buy_price=30,
                sell_price=5,
                level_required=1,
                is_consumable=True,
                emoji="🧪"
            ),
            RPGItem(
                name="Greater Health Potion",
                description="Restores 150 HP",
                rarity=RPGItemRarity.RARE,
                slot=RPGItemSlot.CONSUMABLE,
                health_restore=150,
                buy_price=100,
                sell_price=20,
                level_required=10,
                is_consumable=True,
                emoji="⚗️"
            ),

            # Accessories
            RPGItem(
                name="Lucky Charm",
                description="Increases your luck",
                rarity=RPGItemRarity.EPIC,
                slot=RPGItemSlot.ACCESSORY,
                luck_bonus=10,
                buy_price=800,
                sell_price=150,
                level_required=8,
                emoji="🍀"
            ),
        ]

        session.add_all(items)
        session.commit()
        logger.info(f"✅ Seeded {len(items)} RPG items")
        return True


def seed_enemies():
    """Seed enemies for battles"""
    with db.session_scope() as session:
        existing = session.query(Enemy).count()
        if existing > 0:
            logger.warning(f"Enemies already exist ({existing}). Skipping.")
            return False

        enemies = [
            # Level 1-5
            Enemy(
                name="Goblin",
                description="A weak goblin warrior",
                level=1,
                health=30,
                attack=5,
                defense=2,
                exp_reward=10,
                gold_min=5,
                gold_max=15,
                loot_table=json.dumps([
                    {"item_id": 1, "chance": 0.3},  # Rusty Sword
                    {"item_id": 4, "chance": 0.4}  # Leather Armor
                ]),
                emoji="👺"
            ),
            Enemy(
                name="Wolf",
                description="A hungry wolf",
                level=3,
                health=50,
                attack=8,
                defense=3,
                exp_reward=20,
                gold_min=10,
                gold_max=25,
                loot_table=json.dumps([
                    {"item_id": 7, "chance": 0.5}  # Health Potion
                ]),
                emoji="🐺"
            ),

            # Level 5-10
            Enemy(
                name="Orc Warrior",
                description="A strong orc with battle scars",
                level=7,
                health=100,
                attack=15,
                defense=8,
                exp_reward=50,
                gold_min=30,
                gold_max=60,
                loot_table=json.dumps([
                    {"item_id": 2, "chance": 0.3},  # Steel Sword
                    {"item_id": 6, "chance": 0.4}  # Iron Helmet
                ]),
                emoji="🧌"
            ),
            Enemy(
                name="Giant Spider",
                description="A massive venomous spider",
                level=10,
                health=150,
                attack=20,
                defense=10,
                exp_reward=80,
                gold_min=50,
                gold_max=100,
                loot_table=json.dumps([
                    {"item_id": 5, "chance": 0.2},  # Steel Plate
                    {"item_id": 8, "chance": 0.3}  # Greater Health Potion
                ]),
                emoji="🕷️"
            ),

            # Level 15+
            Enemy(
                name="Dark Knight",
                description="A cursed knight in black armor",
                level=15,
                health=250,
                attack=35,
                defense=20,
                exp_reward=150,
                gold_min=100,
                gold_max=200,
                loot_table=json.dumps([
                    {"item_id": 5, "chance": 0.5},  # Steel Plate
                    {"item_id": 9, "chance": 0.3}  # Lucky Charm
                ]),
                emoji="⚔️"
            ),
            Enemy(
                name="Dragon Whelp",
                description="A young dragon, still dangerous",
                level=20,
                health=400,
                attack=50,
                defense=25,
                exp_reward=300,
                gold_min=200,
                gold_max=400,
                loot_table=json.dumps([
                    {"item_id": 3, "chance": 0.1},  # Dragon Slayer
                    {"item_id": 9, "chance": 0.4}  # Lucky Charm
                ]),
                emoji="🐲"
            ),
        ]

        session.add_all(enemies)
        session.commit()
        logger.info(f"✅ Seeded {len(enemies)} enemies")
        return True


def seed_daily_quests():
    """Seed daily quests"""
    with db.session_scope() as session:
        existing = session.query(DailyQuest).count()
        if existing > 0:
            logger.warning(f"Daily quests already exist ({existing}). Skipping.")
            return False

        quests = [
            DailyQuest(
                name="Battle Training",
                description="Win 3 battles against any enemy",
                quest_type="win_battles",
                target=3,
                exp_reward=100,
                gold_reward=100,
                gem_reward=5
            ),
            DailyQuest(
                name="Monster Slayer",
                description="Defeat 5 enemies",
                quest_type="battle",
                target=5,
                exp_reward=150,
                gold_reward=150,
                gem_reward=10
            ),
            DailyQuest(
                name="Damage Dealer",
                description="Deal 500 total damage",
                quest_type="deal_damage",
                target=500,
                exp_reward=200,
                gold_reward=200,
                gem_reward=15
            ),
        ]

        session.add_all(quests)
        session.commit()
        logger.info(f"✅ Seeded {len(quests)} daily quests")
        return True


def seed_mo2_items(guild_id: int):
    """Seed Mortal Online 2 items"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            logger.error(f"Guild {guild_id} not found")
            return False

        # Get or create MO2 game
        mo2 = session.query(Game).filter_by(
            guild_id=guild.id,
            name="Mortal Online 2"
        ).first()

        if not mo2:
            mo2 = Game(guild_id=guild.id, name="Mortal Online 2", enabled=True)
            session.add(mo2)
            session.flush()

        # Check if categories exist
        existing_cats = session.query(GameItemCategory).filter_by(game_id=mo2.id).count()
        if existing_cats > 0:
            logger.warning("MO2 categories already exist. Skipping.")
            return False

        # Create categories
        weapon_cat = GameItemCategory(
            game_id=mo2.id,
            name="Weapons",
            item_type=ItemType.WEAPON,
            description="All weapons in MO2"
        )
        session.add(weapon_cat)
        session.flush()

        armor_cat = GameItemCategory(
            game_id=mo2.id,
            name="Armor",
            item_type=ItemType.ARMOR,
            description="All armor pieces"
        )
        session.add(armor_cat)
        session.flush()

        race_cat = GameItemCategory(
            game_id=mo2.id,
            name="Races",
            item_type=ItemType.RACE,
            description="Playable races"
        )
        session.add(race_cat)
        session.flush()

        # Sample items
        items = [
            # Weapons
            GameItem(
                game_id=mo2.id,
                category_id=weapon_cat.id,
                name="Steel Sword",
                item_type=ItemType.WEAPON,
                description="A standard steel longsword",
                stats=json.dumps({
                    "damage": 45,
                    "durability": 100,
                    "weight": 3.5,
                    "handle_hits": "slashing"
                }),
                tags="sword, melee, steel"
            ),
            GameItem(
                game_id=mo2.id,
                category_id=weapon_cat.id,
                name="Asymmetrical Bow",
                item_type=ItemType.WEAPON,
                description="A powerful asymmetrical bow",
                stats=json.dumps({
                    "damage": 60,
                    "range": 80,
                    "durability": 80,
                    "weight": 2.0,
                    "strength_requirement": 85
                }),
                tags="bow, ranged, asymmetrical"
            ),

            # Armor
            GameItem(
                game_id=mo2.id,
                category_id=armor_cat.id,
                name="Steel Full Helmet",
                item_type=ItemType.ARMOR,
                description="Full steel helmet providing excellent protection",
                stats=json.dumps({
                    "armor": 25,
                    "weight": 4.5,
                    "durability": 150,
                    "slot": "head"
                }),
                tags="helmet, steel, heavy"
            ),

            # Races
            GameItem(
                game_id=mo2.id,
                category_id=race_cat.id,
                name="Thursar",
                item_type=ItemType.RACE,
                description="Half-giant race with exceptional strength",
                stats=json.dumps({
                    "strength_bonus": 10,
                    "size_bonus": 8,
                    "dexterity_penalty": -5,
                    "intelligence_penalty": -3,
                    "max_health": 125
                }),
                tags="race, thursar, half-giant"
            ),
            GameItem(
                game_id=mo2.id,
                category_id=race_cat.id,
                name="Alvarin",
                item_type=ItemType.RACE,
                description="Elf-like race with high dexterity and speed",
                stats=json.dumps({
                    "dexterity_bonus": 8,
                    "psyche_bonus": 5,
                    "strength_penalty": -5,
                    "size_penalty": -3,
                    "speed_bonus": 10
                }),
                tags="race, alvarin, elf"
            ),
        ]

        session.add_all(items)
        session.commit()
        logger.info(f"✅ Seeded {len(items)} MO2 items")
        return True


def seed_all(guild_id: int):
    """Seed all game data"""
    logger.info(f"Starting game data seed for guild {guild_id}")

    success = True

    if not seed_rpg_items():
        success = False

    if not seed_enemies():
        success = False

    if not seed_daily_quests():
        success = False

    if not seed_mo2_items(guild_id):
        success = False

    if success:
        logger.info("\n✅ Game data seed completed successfully!")
        logger.info("\nAvailable commands:")
        logger.info("\n🎮 RPG Mini-Game:")
        logger.info("  /profile - View your RPG profile")
        logger.info("  /battle - Fight enemies and earn rewards")
        logger.info("  /inventory - View your items")
        logger.info("  /equip <id> - Equip items")
        logger.info("  /daily - Claim daily rewards")
        logger.info("  /leaderboard - View rankings")
        logger.info("\n📚 Game Items Database:")
        logger.info("  /item_search - Search for items")
        logger.info("  /item_view <id> - View item details")
        logger.info("  /item_list - List all items")
        logger.info("\n⚙️ Admin Commands:")
        logger.info("  /item_add - Add new item to database")
        logger.info("  /item_edit <id> - Edit existing item")
        logger.info("  /item_category_add - Add item category")
    else:
        logger.warning("\n⚠️ Seed process completed with warnings")

    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_game_data.py <guild_id> [--dev]`")
        print("\nThis will seed:")
        print("  • RPG items (weapons, armor, potions)")
        print("  • Enemies for battles")
        print("  • Daily quests")
        print("  • Sample Mortal Online 2 items")
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