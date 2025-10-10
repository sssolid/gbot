# File: models_rpg.py
# Location: /bot/models_rpg.py
# Additional models for rpg system

from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime, Text,
    ForeignKey, Float, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.types import TypeDecorator, String as SQLString
from datetime import datetime
import enum

from utils.enum_as_string import EnumAsString

from models import Base


# ============================================================================
# RPG MINI-GAME SYSTEM
# ============================================================================

class UserProfile(Base):
    """Extended user profile for RPG mini-game"""
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False, unique=True)

    # Leveling
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    next_level_exp = Column(Integer, default=100)

    # Stats
    max_health = Column(Integer, default=100)
    current_health = Column(Integer, default=100)
    attack = Column(Integer, default=10)
    defense = Column(Integer, default=5)
    luck = Column(Integer, default=5)

    # Currency
    gold = Column(Integer, default=100)
    gems = Column(Integer, default=0)

    # Progression
    total_battles = Column(Integer, default=0)
    battles_won = Column(Integer, default=0)
    total_damage_dealt = Column(BigInteger, default=0)
    total_damage_taken = Column(BigInteger, default=0)

    # Timestamps
    last_daily_claim = Column(DateTime, nullable=True)
    last_battle = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    member = relationship('Member', backref='rpg_profile')
    inventory = relationship('InventoryItem', back_populates='profile', cascade='all, delete-orphan')
    max_inventory_slots = Column(Integer, default=20)
    current_inventory_slots = Column(Integer, default=0)
    equipped_items = relationship('EquippedItem', back_populates='profile', cascade='all, delete-orphan')
    battle_history = relationship('BattleLog', back_populates='profile', cascade='all, delete-orphan')


class RPGItemRarity(enum.Enum):
    """Item rarity levels"""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"


class RPGItemSlot(enum.Enum):
    """Equipment slots"""
    WEAPON = "weapon"
    HEAD = "head"
    CHEST = "chest"
    LEGS = "legs"
    FEET = "feet"
    HANDS = "hands"
    ACCESSORY = "accessory"
    CONSUMABLE = "consumable"


class RPGItem(Base):
    """Items for the RPG mini-game"""
    __tablename__ = 'rpg_items'

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rarity = Column(EnumAsString(RPGItemRarity), default=RPGItemRarity.COMMON)
    slot = Column(EnumAsString(RPGItemSlot), nullable=False)

    # Stats bonuses
    attack_bonus = Column(Integer, default=0)
    defense_bonus = Column(Integer, default=0)
    health_bonus = Column(Integer, default=0)
    luck_bonus = Column(Integer, default=0)

    # Consumable effects
    health_restore = Column(Integer, default=0)

    # Economy
    buy_price = Column(Integer, default=0)
    sell_price = Column(Integer, default=0)

    # Level requirement
    level_required = Column(Integer, default=1)

    # Visual
    emoji = Column(String(20), nullable=True)

    # Metadata
    is_tradeable = Column(Boolean, default=True)
    is_consumable = Column(Boolean, default=False)

    inventory_items = relationship('InventoryItem', back_populates='item', cascade='all, delete-orphan')


class InventoryItem(Base):
    """User's inventory"""
    __tablename__ = 'inventory_items'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    quantity = Column(Integer, default=1)
    acquired_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('UserProfile', back_populates='inventory')
    item = relationship('RPGItem', back_populates='inventory_items')


class EquippedItem(Base):
    """Currently equipped items"""
    __tablename__ = 'equipped_items'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)
    slot = Column(EnumAsString(RPGItemSlot), nullable=False)

    equipped_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('UserProfile', back_populates='equipped_items')
    item = relationship('RPGItem')


class Enemy(Base):
    """Enemies for battles"""
    __tablename__ = 'enemies'

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Stats
    level = Column(Integer, default=1)
    health = Column(Integer, default=50)
    attack = Column(Integer, default=5)
    defense = Column(Integer, default=2)

    # Rewards
    exp_reward = Column(Integer, default=10)
    gold_min = Column(Integer, default=5)
    gold_max = Column(Integer, default=15)

    # Loot table (JSON: [{"item_id": 1, "chance": 0.1}, ...])
    loot_table = Column(JSON, nullable=True)

    # Visual
    emoji = Column(String(20), nullable=True)

    battles = relationship('BattleLog', back_populates='enemy', cascade='all, delete-orphan')


class BattleLog(Base):
    """Battle history"""
    __tablename__ = 'battle_logs'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    enemy_id = Column(Integer, ForeignKey('enemies.id'), nullable=False)

    # Results
    won = Column(Boolean, default=False)
    damage_dealt = Column(Integer, default=0)
    damage_taken = Column(Integer, default=0)
    exp_gained = Column(Integer, default=0)
    gold_gained = Column(Integer, default=0)

    # Loot (JSON array of item IDs)
    loot_gained = Column(JSON, nullable=True)

    battle_timestamp = Column(DateTime, default=datetime.utcnow)

    profile = relationship('UserProfile', back_populates='battle_history')
    enemy = relationship('Enemy', back_populates='battles')


class DailyQuest(Base):
    """Daily quests/challenges"""
    __tablename__ = 'daily_quests'

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)

    # Quest type: "battle", "win_battles", "deal_damage", etc.
    quest_type = Column(String(50), nullable=False)

    # Target (e.g., 5 for "win 5 battles")
    target = Column(Integer, default=1)

    # Rewards
    exp_reward = Column(Integer, default=50)
    gold_reward = Column(Integer, default=50)
    gem_reward = Column(Integer, default=0)

    # Can also reward items (JSON array of item IDs)
    item_rewards = Column(JSON, nullable=True)

    # Active status
    is_active = Column(Boolean, default=True)


class UserQuestProgress(Base):
    """Track user progress on daily quests"""
    __tablename__ = 'user_quest_progress'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    quest_id = Column(Integer, ForeignKey('daily_quests.id'), nullable=False)

    progress = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    claimed = Column(Boolean, default=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    profile = relationship('UserProfile')
    quest = relationship('DailyQuest')


class Trade(Base):
    """Trading between users"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)

    # Traders
    sender_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    receiver_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    # Offer (JSON: {"gold": 100, "items": [{"item_id": 1, "quantity": 2}]})
    sender_offer = Column(JSON, nullable=False)
    receiver_offer = Column(JSON, nullable=False)

    # Status
    status = Column(String(20), default="pending")  # pending, accepted, rejected, cancelled

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    sender = relationship('UserProfile', foreign_keys=[sender_profile_id])
    receiver = relationship('UserProfile', foreign_keys=[receiver_profile_id])


class Leaderboard(Base):
    """Cached leaderboard data"""
    __tablename__ = 'leaderboards'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    # Rankings
    level_rank = Column(Integer, nullable=True)
    gold_rank = Column(Integer, nullable=True)
    battles_rank = Column(Integer, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow)

    guild = relationship('Guild')
    profile = relationship('UserProfile')


# ============================================================================
# RAID SYSTEM
# ============================================================================

class RaidStatus(enum.Enum):
    """Raid states"""
    WAITING = "waiting"  # Waiting for players
    IN_PROGRESS = "in_progress"  # Active raid
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Raid failed/timeout


class RaidDifficulty(enum.Enum):
    """Raid difficulty levels"""
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    NIGHTMARE = "nightmare"


class Raid(Base):
    """Active raid instance"""
    __tablename__ = 'raids'

    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)

    # Raid info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(EnumAsString(RaidDifficulty), default=RaidDifficulty.NORMAL)

    # Status
    status = Column(EnumAsString(RaidStatus), default=RaidStatus.WAITING)
    current_wave = Column(Integer, default=1)
    max_waves = Column(Integer, default=3)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Requirements
    min_players = Column(Integer, default=3)
    max_players = Column(Integer, default=10)
    min_level = Column(Integer, default=1)

    # Discord message for tracking
    message_id = Column(BigInteger, nullable=True)
    channel_id = Column(BigInteger, nullable=True)

    guild = relationship('Guild')
    participants = relationship('RaidParticipant', back_populates='raid', cascade='all, delete-orphan')
    waves = relationship('RaidWave', back_populates='raid', cascade='all, delete-orphan')
    loot_drops = relationship('RaidLoot', back_populates='raid', cascade='all, delete-orphan')


class RaidWave(Base):
    """Wave configuration for raids"""
    __tablename__ = 'raid_waves'

    id = Column(Integer, primary_key=True)
    raid_id = Column(Integer, ForeignKey('raids.id'), nullable=False)

    wave_number = Column(Integer, nullable=False)
    is_boss = Column(Boolean, default=False)

    # Enemies in this wave (JSON: [{"enemy_id": 1, "count": 5}, ...])
    enemies = Column(JSON, nullable=False)

    # Wave status
    completed = Column(Boolean, default=False)
    total_enemy_health = Column(Integer, nullable=True)
    remaining_health = Column(Integer, nullable=True)

    raid = relationship('Raid', back_populates='waves')


class RaidParticipant(Base):
    """Player participation in raid"""
    __tablename__ = 'raid_participants'

    id = Column(Integer, primary_key=True)
    raid_id = Column(Integer, ForeignKey('raids.id'), nullable=False)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    # Stats
    damage_dealt = Column(Integer, default=0)
    damage_taken = Column(Integer, default=0)
    healing_done = Column(Integer, default=0)

    # Status
    is_alive = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    raid = relationship('Raid', back_populates='participants')
    profile = relationship('UserProfile')


class RaidLoot(Base):
    """Loot dropped from raid"""
    __tablename__ = 'raid_loot'

    id = Column(Integer, primary_key=True)
    raid_id = Column(Integer, ForeignKey('raids.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    # Rolling info
    winner_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=True)
    roll_closes_at = Column(DateTime, nullable=True)

    raid = relationship('Raid', back_populates='loot_drops')
    item = relationship('RPGItem')
    winner = relationship('UserProfile', foreign_keys=[winner_profile_id])
    rolls = relationship('LootRoll', back_populates='loot', cascade='all, delete-orphan')


class RollType(enum.Enum):
    """Loot roll types"""
    NEED = "need"
    GREED = "greed"
    PASS = "pass"


class LootRoll(Base):
    """Individual player's loot roll"""
    __tablename__ = 'loot_rolls'

    id = Column(Integer, primary_key=True)
    loot_id = Column(Integer, ForeignKey('raid_loot.id'), nullable=False)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    roll_type = Column(EnumAsString(RollType), nullable=False)
    roll_value = Column(Integer, nullable=True)  # 1-100, None if pass

    rolled_at = Column(DateTime, default=datetime.utcnow)

    loot = relationship('RaidLoot', back_populates='rolls')
    profile = relationship('UserProfile')


# ============================================================================
# SHOP SYSTEM
# ============================================================================

class ShopItem(Base):
    """Items available in NPC shop"""
    __tablename__ = 'shop_items'

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    # Pricing
    buy_price = Column(Integer, nullable=False)
    stock = Column(Integer, default=-1)  # -1 = unlimited

    # Availability
    is_available = Column(Boolean, default=True)
    requires_level = Column(Integer, default=1)

    # Restock
    last_restock = Column(DateTime, default=datetime.utcnow)
    restock_interval = Column(Integer, default=86400)  # seconds

    item = relationship('RPGItem')


class PlayerMarketListing(Base):
    """Player-to-player marketplace"""
    __tablename__ = 'player_market_listings'

    id = Column(Integer, primary_key=True)
    seller_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    quantity = Column(Integer, default=1)
    price_per_item = Column(Integer, nullable=False)

    # Status
    is_active = Column(Boolean, default=True)
    listed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Sale info
    buyer_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=True)
    sold_at = Column(DateTime, nullable=True)

    seller = relationship('UserProfile', foreign_keys=[seller_profile_id])
    buyer = relationship('UserProfile', foreign_keys=[buyer_profile_id])
    item = relationship('RPGItem')


class TransactionLog(Base):
    """Track all transactions"""
    __tablename__ = 'transaction_logs'

    id = Column(Integer, primary_key=True)

    # Parties
    seller_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=True)
    buyer_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    # Transaction
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)
    quantity = Column(Integer, default=1)
    price_paid = Column(Integer, nullable=False)

    # Type: 'npc_shop', 'player_market', 'player_trade'
    transaction_type = Column(String(20), nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    seller = relationship('UserProfile', foreign_keys=[seller_profile_id])
    buyer = relationship('UserProfile', foreign_keys=[buyer_profile_id])
    item = relationship('RPGItem')


# ============================================================================
# PLAYER STRUCTURES / HOUSING
# ============================================================================

class StructureType(enum.Enum):
    """Types of structures"""
    SMALL_STORAGE = "small_storage"  # +10 slots
    MEDIUM_STORAGE = "medium_storage"  # +25 slots
    LARGE_STORAGE = "large_storage"  # +50 slots
    WAREHOUSE = "warehouse"  # +100 slots
    WORKSHOP = "workshop"  # Crafting bonus
    FORGE = "forge"  # Weapon crafting
    VAULT = "vault"  # Secure storage


class PlayerStructure(Base):
    """Player-owned structures"""
    __tablename__ = 'player_structures'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    structure_type = Column(EnumAsString(StructureType), nullable=False)
    name = Column(String(100), nullable=True)  # Custom name

    # Capacity
    max_capacity = Column(Integer, default=10)
    current_usage = Column(Integer, default=0)

    # Cost and maintenance
    build_cost = Column(Integer, nullable=False)
    upkeep_cost = Column(Integer, default=0)  # Per week
    last_upkeep_paid = Column(DateTime, default=datetime.utcnow)

    # Status
    is_active = Column(Boolean, default=True)
    built_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship('UserProfile', backref='structures')
    stored_items = relationship('StructureStorage', back_populates='structure', cascade='all, delete-orphan')


class StructureStorage(Base):
    """Items stored in structures"""
    __tablename__ = 'structure_storage'

    id = Column(Integer, primary_key=True)
    structure_id = Column(Integer, ForeignKey('player_structures.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    quantity = Column(Integer, default=1)
    stored_at = Column(DateTime, default=datetime.utcnow)

    structure = relationship('PlayerStructure', back_populates='stored_items')
    item = relationship('RPGItem')


# ============================================================================
# ROGUELIKE DUNGEON SYSTEM
# ============================================================================

class DungeonStatus(enum.Enum):
    """Dungeon run status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    DIED = "died"


class DungeonDifficulty(enum.Enum):
    """Dungeon difficulty"""
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    INSANE = "insane"


class DungeonRun(Base):
    """Active dungeon exploration"""
    __tablename__ = 'dungeon_runs'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)

    # Dungeon info
    name = Column(String(100), nullable=False)
    difficulty = Column(EnumAsString(DungeonDifficulty), default=DungeonDifficulty.NORMAL)
    seed = Column(String(50), nullable=True)  # For regeneration

    # Progress
    current_floor = Column(Integer, default=1)
    max_floor = Column(Integer, default=10)
    current_room = Column(Integer, default=0)

    # Status
    status = Column(EnumAsString(DungeonStatus), default=DungeonStatus.ACTIVE)

    # Stats
    monsters_killed = Column(Integer, default=0)
    treasure_found = Column(Integer, default=0)
    rooms_explored = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Current state (JSON: {"position": [x, y], "health": 100, "map": [...], "visible": [...]})
    state = Column(JSON, nullable=True)

    profile = relationship('UserProfile', backref='dungeon_runs')


class DungeonRoom(Base):
    """Room types and configurations"""
    __tablename__ = 'dungeon_rooms'

    id = Column(Integer, primary_key=True)

    # Room type: 'combat', 'treasure', 'shop', 'boss', 'rest', 'trap'
    room_type = Column(String(20), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # ASCII/emoji representation
    visual = Column(Text, nullable=True)

    # Encounters (JSON: [{"enemy_id": 1, "count": 3}, ...])
    encounters = Column(JSON, nullable=True)

    # Loot (JSON: [{"item_id": 1, "chance": 0.3}, ...])
    loot_table = Column(JSON, nullable=True)

    # Difficulty range
    min_floor = Column(Integer, default=1)
    max_floor = Column(Integer, nullable=True)


class DungeonLoot(Base):
    """Loot found in dungeons"""
    __tablename__ = 'dungeon_loot'

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('dungeon_runs.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)

    quantity = Column(Integer, default=1)
    floor_found = Column(Integer, nullable=False)
    found_at = Column(DateTime, default=datetime.utcnow)

    run = relationship('DungeonRun')
    item = relationship('RPGItem')


# ============================================================================
# CRAFTING SYSTEM (Bonus!)
# ============================================================================

class Recipe(Base):
    """Crafting recipes"""
    __tablename__ = 'recipes'

    id = Column(Integer, primary_key=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Result
    result_item_id = Column(Integer, ForeignKey('rpg_items.id'), nullable=False)
    result_quantity = Column(Integer, default=1)

    # Requirements (JSON: [{"item_id": 1, "quantity": 5}, ...])
    ingredients = Column(JSON, nullable=False)

    # Restrictions
    requires_level = Column(Integer, default=1)
    requires_structure = Column(EnumAsString(StructureType), nullable=True)

    # Costs
    gold_cost = Column(Integer, default=0)
    craft_time = Column(Integer, default=0)  # Seconds

    result_item = relationship('RPGItem')


class CraftingQueue(Base):
    """Active crafting jobs"""
    __tablename__ = 'crafting_queue'

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    recipe_id = Column(Integer, ForeignKey('recipes.id'), nullable=False)

    quantity = Column(Integer, default=1)

    started_at = Column(DateTime, default=datetime.utcnow)
    completes_at = Column(DateTime, nullable=False)
    completed = Column(Boolean, default=False)

    profile = relationship('UserProfile')
    recipe = relationship('Recipe')