"""
Main bot class with event handlers and cog loading - FIXED VERSION
"""
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from database import GuildConfig, setup_database
from utils.cache import ConfigCache
from utils.permissions import PermissionChecker

logger = logging.getLogger(__name__)


class GuildBot(commands.Bot):
    """Main bot class for the Guild Management Bot."""
    
    def __init__(self, database_url: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database_url = database_url
        self.config_cache = ConfigCache()
        self.permission_checker = PermissionChecker()
        self._ready = False
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Bot setup started")
        
        # Initialize database first
        try:
            await setup_database(self.database_url)
            logger.info("Database connection established")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        
        # Load all cogs
        cogs = [
            'cogs.onboarding',
            'cogs.profiles', 
            'cogs.polls',
            'cogs.moderation',
            'cogs.announcements',
            'cogs.configuration'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
        
        # Load context menus
        try:
            await self.load_extension('context_menus')
            logger.info("Loaded context menus")
        except Exception as e:
            logger.error(f"Failed to load context menus: {e}")
        
        # DEV: Sync commands to specific guild for instant availability
        guild_id_str = os.getenv("GUILD_ID", "")
        if guild_id_str.isdigit():
            guild_id = int(guild_id_str)
            guild_obj = discord.Object(id=guild_id)
            try:
                # Copy global commands to guild and sync
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                logger.info(f"Guild-scoped sync: {len(synced)} commands → {guild_id}")
            except Exception as e:
                logger.error(f"Failed to sync guild commands: {e}")
        
        # Always sync globally as well
        try:
            synced = await self.tree.sync()
            logger.info(f"Global sync: {len(synced)} commands")
        except Exception as e:
            logger.error(f"Failed to sync global commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        if not self._ready:
            # Set activity
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="for /setup | UI-first guild management"
                ),
                status=discord.Status.online # type: ignore[arg-type]
            )

            logger.info(f"Bot ready: {self.user} (ID: {self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} guilds")

            # Load persistent views
            try:
                from views.panels import AdminDashboard, MemberHub
                self.add_view(AdminDashboard())
                self.add_view(MemberHub())
                logger.info("Persistent views loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load persistent views: {e}")

            self._ready = True

    @staticmethod
    async def on_guild_join(guild: discord.Guild):
        """Called when the bot joins a new guild."""
        logger.info(f"Joined guild: {guild.name} ({guild.id})")

        # Send welcome message
        try:
            embed = discord.Embed(
                title="🎉 Thanks for adding Guild Management Bot!",
                description=(
                    "I'm here to help manage your guild with powerful features:\n\n"
                    "• **Onboarding System** - Custom questions and role assignment\n"
                    "• **Character Profiles** - Member character management\n"
                    "• **Polls & Voting** - Community engagement tools\n"
                    "• **Auto-Moderation** - Spam and content filtering\n"
                    "• **Announcements** - Scheduled server announcements\n\n"
                    "**Get Started:**\n"
                    "1. Use `/setup` to configure basic settings\n"
                    "2. Deploy control panels with `/deploy_panels`\n"
                    "3. Check out `/help` for all available commands"
                ),
                color=discord.Color.green()
            )

            embed.add_field(
                name="🔗 Important Links",
                value=(
                    "• [Documentation](https://docs.example.com)\n"
                    "• [Support Server](https://discord.gg/example)\n"
                    "• [GitHub](https://github.com/example/repo)"
                ),
                inline=False
            )

            embed.set_footer(text="Use /help to see all available commands")

            # Try to send to system channel, then any text channel
            target_channel = (
                guild.system_channel or
                next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
            )

            if target_channel:
                await target_channel.send(embed=embed)
                logger.info(f"Sent welcome message to {guild.name}")

        except (discord.Forbidden, discord.HTTPException, discord.NotFound) as e:
            logger.error(f"Failed to send welcome message to {guild.name}: {e}")

    async def on_guild_remove(self, guild: discord.Guild):
        """Called when the bot leaves a guild."""
        logger.info(f"Left guild: {guild.name} ({guild.id})")

        # Clean up cached data
        if hasattr(self, 'config_cache'):
            self.config_cache.invalidate_guild_cache(guild.id)

    @staticmethod
    async def on_application_command_error(interaction: discord.Interaction, error: Exception):
        """Handle application command errors."""
        logger.error(f"Command error in {interaction.command}: {error}", exc_info=True)

        embed = discord.Embed(
            title="❌ Command Error",
            description="An error occurred while processing your command.",
            color=discord.Color.red()
        )

        if isinstance(error, commands.MissingPermissions):
            embed.description = "You don't have permission to use this command."
        elif isinstance(error, commands.BotMissingPermissions):
            embed.description = "I don't have the necessary permissions to execute this command."
        elif isinstance(error, commands.CommandOnCooldown):
            embed.description = f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."
        else:
            embed.description = "An unexpected error occurred. Please try again later."

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass  # Couldn't send error message

    async def on_error(self, event: str, *args, **kwargs):
        """Handle general bot errors."""
        logger.error(f"Bot error in event {event}", exc_info=True)

    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration through cache."""
        return await self.config_cache.get_guild_config(guild_id)

    async def update_guild_config(self, guild_id: int, **kwargs) -> GuildConfig:
        """Update guild configuration through cache."""
        return await self.config_cache.update_guild_config(guild_id, **kwargs)

    async def log_action(self, guild_id: int, action: str, moderator: discord.Member,
                        target: discord.Member, details: str = None):
        """Log an administrative action."""
        try:
            guild_config = await self.get_guild_config(guild_id)
            if guild_config and guild_config.logs_channel_id:
                logs_channel = self.get_channel(guild_config.logs_channel_id)
                if logs_channel:
                    embed = discord.Embed(
                        title=f"📋 {action}",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )

                    embed.add_field(
                        name="Moderator",
                        value=f"{moderator.mention}\n**ID:** {moderator.id}",
                        inline=True
                    )

                    embed.add_field(
                        name="Target",
                        value=f"{target.mention}\n**ID:** {target.id}",
                        inline=True
                    )

                    if details:
                        embed.add_field(
                            name="Details",
                            value=details,
                            inline=False
                        )

                    await logs_channel.send(embed=embed)

        except (discord.Forbidden, discord.HTTPException, discord.NotFound) as e:
            logger.error(f"Failed to log action: {e}")

    async def close(self):
        """Clean shutdown of the bot."""
        logger.info("Bot shutting down...")

        # Close database connections
        try:
            from database import close_database
            await close_database()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        await super().close()
        logger.info("Bot shutdown complete")


# Utility function to create bot instance
def create_bot(database_url: str) -> GuildBot:
    """Create and configure the bot instance."""

    # Configure intents
    intents = discord.Intents.default()
    intents.message_content = True  # Required for moderation
    intents.members = True  # Required for member management
    intents.guilds = True

    # Create bot instance
    bot = GuildBot(
        database_url=database_url,
        command_prefix=commands.when_mentioned_or('!'),
        intents=intents,
        help_command=None  # We'll create a custom help system
    )
    
    return bot