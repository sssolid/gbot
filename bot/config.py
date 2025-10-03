# File: config.py
# Location: /bot/config.py

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration from environment variables"""

    # Discord
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    COMMAND_PREFIX = os.getenv('COMMAND_PREFIX', '!')

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Features
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable is required")
        return True