"""
Enhanced main entry point for the Guild Management Bot
"""
import asyncio
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

import discord
from discord.ext import commands

from bot import GuildBot
from database import init_database

# Load environment variables
load_dotenv()

# Configure logging with timezone awareness
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('guild_bot.log'),
        logging.StreamHandler()
    ]
)

# Set timezone-aware logging
dt = datetime.now(timezone.utc)
tt = dt.timetuple()
logging.Formatter.converter = lambda *args: tt

logger = logging.getLogger(__name__)


async def main():
    """Enhanced main function with proper error handling and database initialization."""
    # Validate required environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN environment variable is required!")
        return

    database_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///guild_bot.sqlite')

    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_database(database_url)
        logger.info("Database initialized successfully")

        # Configure bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.guild_messages = True
        intents.reactions = True

        # Create and start bot
        bot = GuildBot(
            database_url=database_url,
            command_prefix='!',
            intents=intents,
            help_command=None
        )

        logger.info("Starting Guild Management Bot...")
        await bot.start(token)

    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        from database import close_database
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutdown requested. Goodbye!")
    except Exception as e:
        print(f"Failed to start bot: {e}")