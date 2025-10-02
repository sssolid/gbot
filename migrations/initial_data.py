"""
Initial database migration for Guild Management Bot
Populates essential onboarding questions and configuration data.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

from database import (
    OnboardingQuestion, OnboardingRule, get_session, setup_database
)

# Default onboarding questions for gaming guilds
DEFAULT_ONBOARDING_QUESTIONS = [
    {
        "qid": "timezone",
        "prompt": "What timezone are you in? This helps us coordinate events and activities.",
        "type": "timezone",
        "required": True,
        "options": None,
        "map_to": "timezone",
        "position": 0
    },
    {
        "qid": "gaming_experience",
        "prompt": "How would you describe your gaming experience level?",
        "type": "single_select",
        "required": True,
        "options": [
            "New to gaming - just getting started",
            "Casual gamer - play for fun occasionally",
            "Regular gamer - play several times a week",
            "Hardcore gamer - gaming is my main hobby",
            "Professional/Competitive player"
        ],
        "map_to": "experience_level",
        "position": 1
    },
    {
        "qid": "primary_games",
        "prompt": "What are your primary games or game genres? (List your top 3-5 games or genres)",
        "type": "text",
        "required": True,
        "options": None,
        "map_to": "primary_games",
        "position": 2
    },
    {
        "qid": "play_style",
        "prompt": "What's your preferred play style?",
        "type": "single_select",
        "required": True,
        "options": [
            "PvE (Player vs Environment) - Dungeons, raids, story content",
            "PvP (Player vs Player) - Competitive multiplayer",
            "Mixed - I enjoy both PvE and PvP content",
            "Social - I prefer group activities and community events",
            "Solo - I mostly play alone but enjoy being part of a community"
        ],
        "map_to": "play_style",
        "position": 3
    },
    {
        "qid": "availability",
        "prompt": "When are you typically available to play? (Select all that apply)",
        "type": "single_select",
        "required": True,
        "options": [
            "Weekday mornings (6am - 12pm)",
            "Weekday afternoons (12pm - 6pm)",
            "Weekday evenings (6pm - 12am)",
            "Weekday late night (12am - 6am)",
            "Weekend mornings (6am - 12pm)",
            "Weekend afternoons (12pm - 6pm)",
            "Weekend evenings (6pm - 12am)",
            "Weekend late night (12am - 6am)",
            "Varies - my schedule changes frequently"
        ],
        "map_to": "availability",
        "position": 4
    },
    {
        "qid": "role_preference",
        "prompt": "In team-based games, what role do you typically prefer?",
        "type": "single_select",
        "required": False,
        "options": [
            "Tank - Frontline, damage absorption, crowd control",
            "DPS - Damage dealing, offense focused",
            "Support/Healer - Team support, healing, buffs",
            "Utility - Specialist roles, unique abilities",
            "Flexible - I can fill any role as needed",
            "Not applicable - I don't play team-based games"
        ],
        "map_to": "role_preference",
        "position": 5
    },
    {
        "qid": "communication",
        "prompt": "Are you comfortable using voice chat during group activities?",
        "type": "single_select",
        "required": True,
        "options": [
            "Yes - I prefer voice chat for coordination",
            "Sometimes - depends on the activity and group size",
            "Text only - I prefer to communicate via text",
            "Listening only - I can listen but prefer not to speak",
            "No voice chat - I avoid voice communication"
        ],
        "map_to": "voice_comfort",
        "position": 6
    },
    {
        "qid": "guild_interest",
        "prompt": "What interests you most about joining our guild?",
        "type": "text",
        "required": True,
        "options": None,
        "map_to": "join_reason",
        "position": 7
    },
    {
        "qid": "previous_guilds",
        "prompt": "Have you been part of gaming communities or guilds before? If so, what was your experience like?",
        "type": "text",
        "required": False,
        "options": None,
        "map_to": "guild_history",
        "position": 8
    },
    {
        "qid": "goals",
        "prompt": "What are you hoping to achieve or experience as part of this community?",
        "type": "text",
        "required": True,
        "options": None,
        "map_to": "community_goals",
        "position": 9
    }
]

# Default role suggestion rules
DEFAULT_ROLE_RULES = [
    {
        "description": "New Gamers Role",
        "when_conditions": [
            {"key": "gaming_experience", "value": "New to gaming - just getting started"}
        ],
        "suggest_roles": ["Newbie", "Beginner", "Learning"]  # Role names - will need to be mapped to IDs
    },
    {
        "description": "Casual Gamer Role",
        "when_conditions": [
            {"key": "gaming_experience", "value": "Casual gamer - play for fun occasionally"}
        ],
        "suggest_roles": ["Casual", "Weekend Warrior"]
    },
    {
        "description": "Hardcore Gamer Role",
        "when_conditions": [
            {"key": "gaming_experience", "value": "Hardcore gamer - gaming is my main hobby"}
        ],
        "suggest_roles": ["Hardcore", "Dedicated", "Core Member"]
    },
    {
        "description": "Competitive Player Role",
        "when_conditions": [
            {"key": "gaming_experience", "value": "Professional/Competitive player"}
        ],
        "suggest_roles": ["Competitive", "Pro Player", "Elite"]
    },
    {
        "description": "PvE Player Role",
        "when_conditions": [
            {"key": "play_style", "value": "PvE (Player vs Environment) - Dungeons, raids, story content"}
        ],
        "suggest_roles": ["PvE", "Raider", "PvE Enthusiast"]
    },
    {
        "description": "PvP Player Role",
        "when_conditions": [
            {"key": "play_style", "value": "PvP (Player vs Player) - Competitive multiplayer"}
        ],
        "suggest_roles": ["PvP", "Gladiator", "PvP Enthusiast"]
    },
    {
        "description": "Tank Role",
        "when_conditions": [
            {"key": "role_preference", "value": "Tank - Frontline, damage absorption, crowd control"}
        ],
        "suggest_roles": ["Tank", "Guardian", "Protector"]
    },
    {
        "description": "DPS Role",
        "when_conditions": [
            {"key": "role_preference", "value": "DPS - Damage dealing, offense focused"}
        ],
        "suggest_roles": ["DPS", "Striker", "Damage Dealer"]
    },
    {
        "description": "Support Role",
        "when_conditions": [
            {"key": "role_preference", "value": "Support/Healer - Team support, healing, buffs"}
        ],
        "suggest_roles": ["Support", "Healer", "Medic"]
    },
    {
        "description": "Voice Chat Comfortable",
        "when_conditions": [
            {"key": "communication", "value": "Yes - I prefer voice chat for coordination"}
        ],
        "suggest_roles": ["Voice Active", "Communicator"]
    },
    {
        "description": "Text Only Communication",
        "when_conditions": [
            {"key": "communication", "value": "Text only - I prefer to communicate via text"}
        ],
        "suggest_roles": ["Text Only", "Quiet Member"]
    }
]


async def populate_onboarding_questions(guild_id: int) -> int:
    """
    Populate default onboarding questions for a guild.

    Args:
        guild_id: The Discord guild ID to populate questions for

    Returns:
        Number of questions added
    """
    async with get_session() as session:
        questions_added = 0

        for question_data in DEFAULT_ONBOARDING_QUESTIONS:
            # Check if question already exists
            from sqlalchemy import select

            existing = await session.execute(
                select(OnboardingQuestion).filter(
                    OnboardingQuestion.guild_id == guild_id,
                    OnboardingQuestion.qid == question_data["qid"]
                )
            )

            if existing.scalar_one_or_none():
                continue  # Skip if already exists

            # Create new question
            question = OnboardingQuestion(
                guild_id=guild_id,
                qid=question_data["qid"],
                prompt=question_data["prompt"],
                type=question_data["type"],
                required=question_data["required"],
                options=question_data["options"],
                map_to=question_data["map_to"],
                position=question_data["position"],
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            session.add(question)
            questions_added += 1

        await session.commit()
        return questions_added


async def populate_role_rules(guild_id: int, role_mapping: Dict[str, int] = None) -> int:
    """
    Populate default role suggestion rules for a guild.

    Args:
        guild_id: The Discord guild ID to populate rules for
        role_mapping: Mapping of role names to role IDs (optional)

    Returns:
        Number of rules added
    """
    async with get_session() as session:
        rules_added = 0

        for rule_data in DEFAULT_ROLE_RULES:
            # Map role names to IDs if mapping provided
            suggested_roles = rule_data["suggest_roles"]
            if role_mapping:
                mapped_roles = []
                for role_name in suggested_roles:
                    if role_name in role_mapping:
                        mapped_roles.append(role_mapping[role_name])
                    else:
                        mapped_roles.append(role_name)  # Keep name if no mapping
                suggested_roles = mapped_roles

            # Create new rule
            rule = OnboardingRule(
                guild_id=guild_id,
                when_conditions=rule_data["when_conditions"],
                suggest_roles=suggested_roles,
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            session.add(rule)
            rules_added += 1

        await session.commit()
        return rules_added


async def run_initial_migration(guild_id: int, role_mapping: Dict[str, int] = None):
    """
    Run the initial migration for a specific guild.

    Args:
        guild_id: The Discord guild ID to populate data for
        role_mapping: Optional mapping of role names to Discord role IDs
    """
    print(f"Running initial migration for guild {guild_id}...")

    try:
        # Ensure database is set up
        await setup_database()

        # Populate onboarding questions
        questions_added = await populate_onboarding_questions(guild_id)
        print(f"Added {questions_added} onboarding questions")

        # Populate role rules
        rules_added = await populate_role_rules(guild_id, role_mapping)
        print(f"Added {rules_added} role suggestion rules")

        print("✅ Initial migration completed successfully!")

        return {
            "questions_added": questions_added,
            "rules_added": rules_added
        }

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        raise


async def run_migration_for_all_guilds():
    """
    Run migration for all configured guilds.
    This is useful when setting up the bot for the first time.
    """
    from database import GuildConfig

    print("Running initial migration for all configured guilds...")

    async with get_session() as session:
        result = await session.execute(
            session.query(GuildConfig.guild_id)
        )
        guild_ids = [row[0] for row in result]

    if not guild_ids:
        print("No guilds configured. Use the setup command first.")
        return

    total_questions = 0
    total_rules = 0

    for guild_id in guild_ids:
        try:
            result = await run_initial_migration(guild_id)
            total_questions += result["questions_added"]
            total_rules += result["rules_added"]
        except Exception as e:
            print(f"Failed migration for guild {guild_id}: {str(e)}")

    print(f"\n📊 Migration Summary:")
    print(f"Guilds processed: {len(guild_ids)}")
    print(f"Total questions added: {total_questions}")
    print(f"Total rules added: {total_rules}")


# Utility function for use in bot commands
async def migrate_guild_data(guild_id: int, bot=None):
    """
    Migrate data for a specific guild with role mapping from Discord guild.

    Args:
        guild_id: Discord guild ID
        bot: Discord bot instance (optional, for role mapping)
    """
    role_mapping = {}

    # If bot is provided, try to map common role names to actual Discord role IDs
    if bot:
        guild = bot.get_guild(guild_id)
        if guild:
            common_role_names = [
                "Newbie", "Beginner", "Learning", "Casual", "Weekend Warrior",
                "Hardcore", "Dedicated", "Core Member", "Competitive", "Pro Player", "Elite",
                "PvE", "Raider", "PvE Enthusiast", "PvP", "Gladiator", "PvP Enthusiast",
                "Tank", "Guardian", "Protector", "DPS", "Striker", "Damage Dealer",
                "Support", "Healer", "Medic", "Voice Active", "Communicator",
                "Text Only", "Quiet Member", "Member", "Verified", "Active"
            ]

            for role in guild.roles:
                if role.name in common_role_names:
                    role_mapping[role.name] = role.id

    return await run_initial_migration(guild_id, role_mapping)


# Quick setup script
async def quick_setup():
    """
    Quick setup script for testing/development.
    Creates sample data for guild ID 123456789 (replace with actual guild ID).
    """
    # Replace this with your actual guild ID for testing
    DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID", None))

    print("🚀 Quick Setup - Creating sample onboarding data...")
    print(f"Guild ID: {DEV_GUILD_ID}")
    print("⚠️  Replace DEV_GUILD_ID with your actual Discord server ID!")

    try:
        result = await run_initial_migration(DEV_GUILD_ID)
        print("\n✅ Quick setup completed!")
        print("Next steps:")
        print("1. Update DEV_GUILD_ID in this script or .env with your Discord server ID")
        print("2. Run the bot and use /setup to configure channels")
        print("3. Use /deploy_panels to add the Admin Dashboard and Member Hub")
        print("4. Test the onboarding process through the Member Hub")

        return result

    except Exception as e:
        print(f"❌ Quick setup failed: {str(e)}")
        print("Make sure your database is properly configured and accessible.")
        raise


if __name__ == "__main__":
    """
    Run this script directly to perform initial migration.
    """
    import sys

    if len(sys.argv) > 1:
        # Guild ID provided as command line argument
        try:
            guild_id = int(sys.argv[1])
            print(f"Running migration for guild {guild_id}")
            asyncio.run(run_initial_migration(guild_id))
        except ValueError:
            print("Invalid guild ID. Please provide a valid integer.")
            sys.exit(1)
    else:
        # Run quick setup
        print("No guild ID provided. Running quick setup...")
        print("Edit the TEST_GUILD_ID variable in this script first!")
        asyncio.run(quick_setup())