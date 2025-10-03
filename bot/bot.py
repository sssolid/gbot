# File: bot.py
# Location: /bot/bot.py

import discord
from discord.ext import commands
import logging
import sys
import asyncio
from pathlib import Path

from config import Config
from database import db
from utils.helpers import get_or_create_guild

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)


class OnboardingBot(commands.Bot):
    """Discord Onboarding & Member Management Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=None
        )

        self.initial_extensions = [
            'cogs.onboarding',
            'cogs.moderation',
            'cogs.characters',
            'cogs.admin'
        ]

    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("Setting up bot...")

        # Initialize database
        try:
            db.create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

        # Load cogs
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")

        # Sync commands
        try:
            self.tree.clear_commands(guild=None)
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for new members | /apply"
            )
        )

        # Register guilds in database
        for guild in self.guilds:
            try:
                await get_or_create_guild(guild.id, guild.name)
                logger.info(f"Registered guild: {guild.name} ({guild.id})")
            except Exception as e:
                logger.error(f"Failed to register guild {guild.id}: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a new guild"""
        logger.info(f"Joined new guild: {guild.name} ({guild.id})")
        await get_or_create_guild(guild.id, guild.name)

        # Send welcome message to system channel or first available channel
        channel = guild.system_channel
        if not channel:
            # Find first text channel we can send to
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break

        if channel:
            embed = discord.Embed(
                title="👋 Thanks for adding me!",
                description=(
                    "I'm here to help manage member onboarding and applications.\n\n"
                    "**Getting Started:**\n"
                    "1. Use `/admin_help` to see all admin commands\n"
                    "2. Set up channels with `/set_channel`\n"
                    "3. Configure roles with `/set_role`\n"
                    "4. Add application questions with `/add_question`\n"
                    "5. Add supported games with `/add_game`\n\n"
                    "Need help? Check the documentation or use `/health` to verify setup."
                ),
                color=discord.Color.blue()
            )

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Cannot send welcome message in guild {guild.id}")

    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", delete_after=10)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(f"❌ {str(error)}", delete_after=10)
        else:
            logger.error(f"Command error: {error}", exc_info=error)
            await ctx.send("❌ An error occurred while processing your command.", delete_after=10)

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        """Global error handler for app commands"""
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        elif isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                f"❌ {str(error)}",
                ephemeral=True
            )
        else:
            logger.error(f"App command error: {error}", exc_info=error)

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your command.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing your command.",
                    ephemeral=True
                )

    async def close(self):
        """Cleanup when bot is shutting down"""
        logger.info("Shutting down bot...")

        # Close database connections
        db.close()

        await super().close()
        logger.info("Bot shutdown complete")


async def main():
    """Main entry point"""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create and run bot
    bot = OnboardingBot()

    try:
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")