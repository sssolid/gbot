"""
Constants for the Guild Management Bot - Mortal Online 2 specific data
"""
from typing import Dict, List

# Mortal Online 2 Character Data
MO2_RACES = [
    "Human",
    "Oghmir",
    "Thursar",
    "Sheevra",
    "Veela",
    "Alvarin",
    "Blainn",
    "Sarducaan",
    "Tindremene",
    "Khurite",
    "Sidoian",
    "Kallardian"
]

MO2_ARCHETYPES = {
    "Warrior": {
        "name": "Warrior",
        "subtypes": [
            "Footfighter", "Mounted Warrior", "Archer", "Mounted Archer",
            "Paladin", "Dreadlord", "Beast Master", "Berserker"
        ]
    },
    "Mage": {
        "name": "Mage",
        "subtypes": [
            "Elementalist", "Necromancer", "Spiritist", "Ecumenical",
            "Mental Magic", "Dominator", "Healer", "Battle Mage"
        ]
    },
    "Hybrid": {
        "name": "Hybrid",
        "subtypes": [
            "Hybrid Fighter", "Hybrid Mage", "Assassin", "Ranger",
            "Mounted Hybrid", "Spellsword", "Death Knight", "Shaman"
        ]
    },
    "Crafter": {
        "name": "Crafter",
        "subtypes": [
            "Weaponsmith", "Armorsmith", "Alchemist", "Chef",
            "Bowyer", "Extractor", "Refiner", "Trader"
        ]
    }
}

MO2_PROFESSIONS = [
    # Combat
    "Archery", "Blocking", "Anatomy", "Aggressive Stance", "Defensive Stance",
    "Marksmanship", "Mounted Archery", "Mounted Combat", "Melee Combat",

    # Magic
    "Ecumenical Spells", "Mental Training", "Mental Offense", "Mental Focus",
    "Elementalism", "Necromancy", "Spiritism", "Thaumaturgy",

    # Crafting
    "Weapon Crafting", "Armor Crafting", "Bow Crafting", "Shield Crafting",
    "Alchemy", "Cooking", "Extraction", "Material Lore",

    # Survival
    "Swimming", "Climbing", "Jumping", "Survival", "Camping",
    "Beast Mastery", "Animal Care", "Veterinary", "Taming",

    # Trade
    "Butchery", "Herbalism", "Fishing", "Mining", "Lumberjacking"
]

# Timezone choices
TIMEZONES = [
    "UTC-12:00", "UTC-11:00", "UTC-10:00", "UTC-09:00", "UTC-08:00",
    "UTC-07:00", "UTC-06:00", "UTC-05:00", "UTC-04:00", "UTC-03:00",
    "UTC-02:00", "UTC-01:00", "UTC+00:00", "UTC+01:00", "UTC+02:00",
    "UTC+03:00", "UTC+04:00", "UTC+05:00", "UTC+06:00", "UTC+07:00",
    "UTC+08:00", "UTC+09:00", "UTC+10:00", "UTC+11:00", "UTC+12:00"
]

# Question types for onboarding
QUESTION_TYPES = [
    ("text", "Text Input"),
    ("single_select", "Single Select"),
    ("multi_select", "Multiple Select"),
    ("timezone", "Timezone Selection"),
    ("race", "Character Race"),
    ("archetype", "Character Archetype"),
    ("profession", "Character Profession")
]

# Common question mappings for rules engine
COMMON_MAPPINGS = [
    "role_preference", "experience_level", "timezone", "playtime",
    "character_race", "character_archetype", "guild_interest",
    "pvp_interest", "pve_interest", "crafting_interest", "trading_interest"
]