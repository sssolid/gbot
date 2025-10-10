# File: models_game_db.py
# Location: /bot/models_game_db.py
# Additional models for game systems

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
# GAME ITEM DATABASE (for MO2, etc.)
# ============================================================================

class ItemType(enum.Enum):
    """Types of items in games"""
    WEAPON = "weapon"
    ARMOR = "armor"
    RESOURCE = "resource"
    CONSUMABLE = "consumable"
    TOOL = "tool"
    NPC = "npc"
    CREATURE = "creature"
    LOCATION = "location"
    RACE = "race"
    SKILL = "skill"
    RECIPE = "recipe"


class GameItemCategory(Base):
    """Categories for organizing game items (e.g., 'Swords', 'Heavy Armor')"""
    __tablename__ = 'game_item_categories'

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    name = Column(String(100), nullable=False)
    item_type = Column(EnumAsString(ItemType), nullable=False)
    parent_category_id = Column(Integer, ForeignKey('game_item_categories.id'), nullable=True)
    description = Column(Text, nullable=True)

    game = relationship('Game', foreign_keys=[game_id])
    parent_category = relationship('GameItemCategory', remote_side=[id], backref='subcategories')
    items = relationship('GameItem', back_populates='category', cascade='all, delete-orphan')


class GameItem(Base):
    """Game items/entities database (weapons, armor, NPCs, etc.)"""
    __tablename__ = 'game_items'

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('game_item_categories.id'), nullable=True)

    name = Column(String(200), nullable=False, index=True)
    item_type = Column(EnumAsString(ItemType), nullable=False)
    description = Column(Text, nullable=True)

    # Dynamic stats stored as JSON (game-specific)
    # Example for weapon: {"damage": 50, "durability": 100, "weight": 5.2}
    # Example for armor: {"defense": 25, "weight": 10, "slot": "chest"}
    # Example for NPC: {"health": 500, "location": "Meduli", "drops": ["Gold", "Leather"]}
    stats = Column(JSON, nullable=True)

    # Media
    icon_url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)

    # Tags for searching (comma-separated or JSON array)
    tags = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(BigInteger, nullable=True)

    game = relationship('Game', backref='items')
    category = relationship('GameItemCategory', back_populates='items')