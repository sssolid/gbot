"""
Discord Guild Management Bot - Main Entry Point
"""
import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

from bot import GuildBot
from database import init_database

from dotenv import load_dotenv
import os

# Load variables from .env into the environment
load_dotenv()


def setup_logging():
    """Configure logging for the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )


async def main():
    """Main entry point for the bot."""
    setup_logging()
    
    # Load environment variables
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError("DISCORD_TOKEN environment variable is required")
    
    database_url = os.getenv('DATABASE_URL', 'sqlite:///guild_bot.sqlite')
    
    # Initialize database
    await init_database(database_url)
    
    # Create bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = GuildBot(
        command_prefix='!',
        intents=intents,
        database_url=database_url
    )
    
    # Start the bot
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())