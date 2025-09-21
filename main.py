"""
Main entry point for the Guild Management Bot - FIXED VERSION
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Suppress some noisy loggers
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.client').setLevel(logging.WARNING)


async def main():
    """Main bot startup function."""
    # Validate required environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN environment variable is required!")
        sys.exit(1)
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL', 'sqlite:///guild_bot.sqlite')
    
    # Import and create bot
    from bot import create_bot
    
    logger.info("Creating bot instance...")
    bot = create_bot(database_url)
    
    try:
        logger.info("Starting Guild Management Bot...")
        logger.info(f"Database URL: {database_url}")
        
        # Start the bot
        async with bot:
            await bot.start(token)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)