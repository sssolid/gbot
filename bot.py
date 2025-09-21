"""
Main bot class with event handlers and cog loading
"""
import os
import logging
from typing import Optional

import discord
from discord.ext import commands
from sqlalchemy import select

from database import GuildConfig, get_session
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
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Bot setup started")
        
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
        
        # Sync app commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
        
        # DEV: publish commands to your guild for instant availability
        guild_id_str = os.getenv("GUILD_ID", "")
        if guild_id_str.isdigit():
            guild_id = int(guild_id_str)
            gobj = discord.Object(id=guild_id)
            # keep global registration AND mirror to your guild for fast updates
            self.tree.copy_global_to(guild=gobj)
            synced = await self.tree.sync(guild=gobj)
            logger.info(f"Guild-scoped sync: {len(synced)} commands → {guild_id}")
        else:
            # fallback: global sync
            synced = await self.tree.sync()
            logger.info(f"Global sync: {len(synced)} commands")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"{self.user} is ready!")
        
        # Restore persistent views for all guilds
        await self.restore_persistent_views()
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a new guild."""
        logger.info(f"Joined guild: {guild.name} ({guild.id})")
        await self.ensure_guild_config(guild.id)
    
    async def on_member_join(self, member: discord.Member):
        """Called when a new member joins."""
        if member.bot:
            return
            
        # Send welcome message with onboarding button
        guild_config = await self.get_guild_config(member.guild.id)
        if guild_config and guild_config.welcome_channel_id:
            welcome_channel = self.get_channel(guild_config.welcome_channel_id)
            if welcome_channel:
                from views.onboarding import WelcomeView
                embed = discord.Embed(
                    title=f"Welcome to {member.guild.name}!",
                    description=f"Hello {member.mention}! Please complete our onboarding process to get started.",
                    color=discord.Color.green()
                )
                await welcome_channel.send(embed=embed, view=WelcomeView())
    
    async def ensure_guild_config(self, guild_id: int) -> GuildConfig:
        """Ensure a guild config exists for the given guild."""
        async with get_session() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if not config:
                config = GuildConfig(guild_id=guild_id)
                session.add(config)
                await session.commit()
                logger.info(f"Created guild config for guild {guild_id}")
            
            return config
    
    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration."""
        return await self.config_cache.get_guild_config(guild_id)
    
    async def restore_persistent_views(self):
        """Restore persistent views for all guilds."""
        from views.panels import AdminDashboard, MemberHub
        
        logger.info("Restoring persistent views...")
        
        async with get_session() as session:
            result = await session.execute(select(GuildConfig))
            configs = result.scalars().all()
            
            for config in configs:
                guild = self.get_guild(config.guild_id)
                if not guild:
                    continue
                
                # Restore Admin Dashboard
                if config.admin_dashboard_channel_id and config.admin_dashboard_message_id:
                    channel = guild.get_channel(config.admin_dashboard_channel_id)
                    if channel:
                        try:
                            message = await channel.fetch_message(config.admin_dashboard_message_id)
                            self.add_view(AdminDashboard(), message_id=config.admin_dashboard_message_id)
                        except discord.NotFound:
                            logger.warning(f"Admin dashboard message not found for guild {guild.id}")
                        except Exception as e:
                            logger.error(f"Error restoring admin dashboard for guild {guild.id}: {e}")
                
                # Restore Member Hub
                if config.member_hub_channel_id and config.member_hub_message_id:
                    channel = guild.get_channel(config.member_hub_channel_id)
                    if channel:
                        try:
                            message = await channel.fetch_message(config.member_hub_message_id)
                            self.add_view(MemberHub(), message_id=config.member_hub_message_id)
                        except discord.NotFound:
                            logger.warning(f"Member hub message not found for guild {guild.id}")
                        except Exception as e:
                            logger.error(f"Error restoring member hub for guild {guild.id}: {e}")
        
        logger.info("Persistent views restored")
    
    async def log_action(self, guild_id: int, action: str, actor: discord.Member, 
                        target: Optional[discord.Member] = None, details: str = ""):
        """Log an action to the guild's log channel."""
        guild_config = await self.get_guild_config(guild_id)
        if not guild_config or not guild_config.logs_channel_id:
            return
        
        log_channel = self.get_channel(guild_config.logs_channel_id)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title=f"🔄 {action}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Actor", value=actor.mention, inline=True)
        
        if target:
            embed.add_field(name="Target", value=target.mention, inline=True)
        
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        
        embed.set_footer(text=f"Guild ID: {guild_id}")
        
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")