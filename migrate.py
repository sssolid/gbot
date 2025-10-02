#!/usr/bin/env python3
"""
Migration runner for Guild Management Bot
Easy script to populate database with initial onboarding questions and rules.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from migrations.initial_data import (
    run_initial_migration, run_migration_for_all_guilds,
    migrate_guild_data, quick_setup
)


def print_help():
    """Print usage help."""
    print("🔧 Guild Management Bot - Database Migration Runner")
    print()
    print("Usage:")
    print("  python migrate.py <command> [options]")
    print()
    print("Commands:")
    print("  init <guild_id>    Initialize onboarding data for specific guild")
    print("  init-all           Initialize data for all configured guilds")
    print("  quick-setup        Quick setup with sample data (for testing)")
    print("  help               Show this help message")
    print()
    print("Examples:")
    print("  python migrate.py init 1234567890123456789")
    print("  python migrate.py init-all")
    print("  python migrate.py quick-setup")
    print()
    print("Environment Variables:")
    print("  DATABASE_URL       Database connection string (optional)")
    print("                     Default: sqlite+aiosqlite:///guild_bot.sqlite")


async def main():
    """Main migration runner function."""
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    try:
        if command == "help" or command == "-h" or command == "--help":
            print_help()

        elif command == "init":
            if len(sys.argv) < 3:
                print("❌ Error: Guild ID required for init command")
                print("Usage: python migrate.py init <guild_id>")
                sys.exit(1)

            try:
                guild_id = int(sys.argv[2])
                print(f"🚀 Initializing onboarding data for guild {guild_id}...")
                result = await run_initial_migration(guild_id)
                print(f"✅ Successfully added {result['questions_added']} questions and {result['rules_added']} rules!")

            except ValueError:
                print("❌ Error: Invalid guild ID. Please provide a valid integer.")
                sys.exit(1)

        elif command == "init-all":
            print("🚀 Initializing onboarding data for all configured guilds...")
            await run_migration_for_all_guilds()
            print("✅ Migration completed for all guilds!")

        elif command == "quick-setup":
            print("🚀 Running quick setup with sample data...")
            await quick_setup()

        else:
            print(f"❌ Unknown command: {command}")
            print("Use 'python migrate.py help' for usage information.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Migration failed with error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure the database is accessible")
        print("2. Check your DATABASE_URL environment variable")
        print("3. Ensure the bot has proper permissions")
        print("4. Try running 'pip install -r requirements.txt' to update dependencies")
        sys.exit(1)


if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("database.py"):
        print("❌ Error: Please run this script from the bot's root directory")
        print("The script should be in the same directory as database.py and main.py")
        sys.exit(1)

    # Run the migration
    asyncio.run(main())