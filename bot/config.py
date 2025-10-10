# File: config.py
# Location: /bot/config.py

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration from environment variables"""

    def __init__(self, dev: bool = False):
        prefix = "DEV_" if dev else ""
        self.GUILD_ID = os.getenv(f"{prefix}GUILD_ID")
        self.DISCORD_TOKEN = os.getenv(f"{prefix}DISCORD_TOKEN")
        self.DATABASE_URL = os.getenv(f"{prefix}DATABASE_URL")
        self.COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if dev else "INFO")
        self.DEBUG_MODE = dev or os.getenv("DEBUG_MODE", "False").lower() == "true"

    def validate(self):
        """Validate required configuration"""
        if not self.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN environment variable is required")
        return True