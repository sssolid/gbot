"""
Moderation cog for the Guild Management Bot - FIXED VERSION
"""
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from typing import Dict, List, Set
from datetime import datetime, timedelta
import re
import asyncio

from database import ModerationIncident, get_session
from views.moderation import ModerationCenterView
from utils.permissions import PermissionChecker, require_moderator, require_admin


class ModerationCog(commands.Cog):
    """Handles moderation features and auto-moderation."""
    
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker: Dict[int, Dict[int, Dict[int, List[datetime]]]] = {}
        self.swear_patterns: Dict[int, Dict[str, re.Pattern]] = {}
        
        # Start the cleanup task
        self.cleanup_task = asyncio.create_task(self.cleanup_spam_tracker())
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        if hasattr(self, 'cleanup_task'):
            self.cleanup_task.cancel()
    
    async def cleanup_spam_tracker(self):
        """Periodically clean up old spam tracking data."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                current_time = datetime.utcnow()
                
                for guild_id in list(self.spam_tracker.keys()):
                    for user_id in list(self.spam_tracker[guild_id].keys()):
                        for channel_id in list(self.spam_tracker[guild_id][user_id].keys()):
                            # Remove messages older than 5 minutes
                            cutoff_time = current_time - timedelta(minutes=5)
                            self.spam_tracker[guild_id][user_id][channel_id] = [
                                msg_time for msg_time in self.spam_tracker[guild_id][user_id][channel_id]
                                if msg_time > cutoff_time
                            ]
                            
                            # Remove empty entries
                            if not self.spam_tracker[guild_id][user_id][channel_id]:
                                del self.spam_tracker[guild_id][user_id][channel_id]
                        
                        if not self.spam_tracker[guild_id][user_id]:
                            del self.spam_tracker[guild_id][user_id]
                    
                    if not self.spam_tracker[guild_id]:
                        del self.spam_tracker[guild_id]
                        
            except Exception as e:
                print(f"Error in spam tracker cleanup: {e}")
    
    @app_commands.command(name="moderation", description="Open the moderation center")
    @require_admin()
    async def moderation_center(self, interaction: discord.Interaction):
        """Open the moderation center interface."""
        view = ModerationCenterView()
        
        embed = discord.Embed(
            title="🛡️ Moderation Center",
            description="Configure and manage server moderation settings.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Available Options",
            value=(
                "• **Spam Filter** - Configure message spam detection\n"
                "• **Swear Filter** - Manage word filtering and actions\n"
                "• **Watch Channels** - Select channels to moderate\n"
                "• **Staff Exemptions** - Set roles exempt from moderation\n"
                "• **Recent Incidents** - View moderation log"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="warn", description="Warn a user")
    @require_moderator()
    async def warn_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        """Warn a user with a reason."""
        if user.bot:
            embed = discord.Embed(
                title="❌ Cannot Warn Bot",
                description="You cannot warn bot users.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if user has higher role than moderator
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            embed = discord.Embed(
                title="❌ Insufficient Permissions",
                description="You cannot warn users with equal or higher roles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create incident record
        async with get_session() as session:
            incident = ModerationIncident(
                guild_id=interaction.guild_id,
                user_id=user.id,
                channel_id=interaction.channel_id,
                type="manual_warn",
                reason=reason,
                action_taken="warn",
                moderator_id=interaction.user.id
            )
            session.add(incident)
            await session.commit()
        
        # Send warning to user via DM
        try:
            user_embed = discord.Embed(
                title="⚠️ Warning",
                description=f"You have been warned in **{interaction.guild.name}**.",
                color=discord.Color.orange()
            )
            user_embed.add_field(name="Reason", value=reason, inline=False)
            user_embed.add_field(
                name="Moderator", 
                value=interaction.user.display_name, 
                inline=True
            )
            await user.send(embed=user_embed)
            dm_status = "✅ DM sent"
        except discord.Forbidden:
            dm_status = "❌ DM failed (disabled)"
        
        # Response to moderator
        embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"Successfully warned {user.mention}.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="DM Status", value=dm_status, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="timeout", description="Timeout a user")
    @require_moderator()
    async def timeout_user(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member, 
        duration: int, 
        unit: str,
        reason: str = "No reason provided"
    ):
        """Timeout a user for a specified duration."""
        if user.bot:
            embed = discord.Embed(
                title="❌ Cannot Timeout Bot",
                description="You cannot timeout bot users.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check permissions
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            embed = discord.Embed(
                title="❌ Insufficient Permissions",
                description="You cannot timeout users with equal or higher roles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate timeout duration
        unit_multipliers = {
            "minutes": 1,
            "hours": 60,
            "days": 1440
        }
        
        if unit not in unit_multipliers:
            embed = discord.Embed(
                title="❌ Invalid Unit",
                description="Unit must be 'minutes', 'hours', or 'days'.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        timeout_minutes = duration * unit_multipliers[unit]
        
        if timeout_minutes > 40320:  # Discord's 28-day limit
            embed = discord.Embed(
                title="❌ Duration Too Long",
                description="Timeout duration cannot exceed 28 days.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        timeout_until = discord.utils.utcnow() + timedelta(minutes=timeout_minutes)
        
        try:
            await user.timeout(timeout_until, reason=f"Timed out by {interaction.user}: {reason}")
            
            # Create incident record
            async with get_session() as session:
                incident = ModerationIncident(
                    guild_id=interaction.guild_id,
                    user_id=user.id,
                    channel_id=interaction.channel_id,
                    type="manual_timeout",
                    reason=reason,
                    action_taken=f"timeout_{timeout_minutes}m",
                    moderator_id=interaction.user.id
                )
                session.add(incident)
                await session.commit()
            
            # Send notification to user
            try:
                user_embed = discord.Embed(
                    title="⏰ Timeout",
                    description=f"You have been timed out in **{interaction.guild.name}**.",
                    color=discord.Color.red()
                )
                user_embed.add_field(name="Duration", value=f"{duration} {unit}", inline=True)
                user_embed.add_field(name="Reason", value=reason, inline=False)
                user_embed.add_field(name="Until", value=discord.utils.format_dt(timeout_until), inline=True)
                await user.send(embed=user_embed)
                dm_status = "✅ DM sent"
            except discord.Forbidden:
                dm_status = "❌ DM failed (disabled)"
            
            # Response to moderator
            embed = discord.Embed(
                title="⏰ User Timed Out",
                description=f"Successfully timed out {user.mention}.",
                color=discord.Color.red()
            )
            embed.add_field(name="Duration", value=f"{duration} {unit}", inline=True)
            embed.add_field(name="Until", value=discord.utils.format_dt(timeout_until), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="DM Status", value=dm_status, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to timeout this user.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title="❌ Timeout Failed",
                description=f"Failed to timeout user: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @timeout_user.autocomplete('unit')
    async def timeout_unit_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for timeout units."""
        units = ['minutes', 'hours', 'days']
        return [
            app_commands.Choice(name=unit, value=unit)
            for unit in units if current.lower() in unit.lower()
        ]
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle message events for auto-moderation."""
        # Skip if message is from a bot or not in a guild
        if message.author.bot or not message.guild:
            return
        
        # Skip if message is from DMs
        if isinstance(message.channel, discord.DMChannel):
            return
        
        # Get moderation config
        if not hasattr(self.bot, 'config_cache'):
            return
        
        config = await self.bot.config_cache.get_moderation_config(message.guild.id)
        if not config:
            return
        
        # Check if user is exempt (staff role)
        staff_roles = config.get('staff_roles', [])
        if any(str(role.id) in staff_roles for role in message.author.roles):
            return
        
        # Check if channel is watched
        watch_channels = config.get('watch_channels', [])
        if watch_channels and str(message.channel.id) not in watch_channels:
            return  # Only moderate watched channels if specified
        
        # Check spam filter
        await self.check_spam_filter(message, config)
        
        # Check swear filter
        await self.check_swear_filter(message, config)
    
    async def check_spam_filter(self, message: discord.Message, config: dict):
        """Check message against spam filter."""
        spam_config = config.get('spam', {})
        if not spam_config.get('enabled', False):
            return
        
        user_id = message.author.id
        channel_id = message.channel.id
        guild_id = message.guild.id
        
        current_time = datetime.utcnow()
        window_seconds = spam_config.get('window_seconds', 10)
        max_messages = spam_config.get('max_messages', 5)
        max_mentions = spam_config.get('max_mentions', 3)
        
        # Initialize tracking
        if guild_id not in self.spam_tracker:
            self.spam_tracker[guild_id] = {}
        if user_id not in self.spam_tracker[guild_id]:
            self.spam_tracker[guild_id][user_id] = {}
        if channel_id not in self.spam_tracker[guild_id][user_id]:
            self.spam_tracker[guild_id][user_id][channel_id] = []
        
        # Clean old messages
        cutoff_time = current_time - timedelta(seconds=window_seconds)
        self.spam_tracker[guild_id][user_id][channel_id] = [
            msg_time for msg_time in self.spam_tracker[guild_id][user_id][channel_id]
            if msg_time > cutoff_time
        ]
        
        # Add current message
        self.spam_tracker[guild_id][user_id][channel_id].append(current_time)
        
        # Check message count
        message_count = len(self.spam_tracker[guild_id][user_id][channel_id])
        mention_count = len(message.mentions)
        
        is_spam = (message_count > max_messages) or (mention_count > max_mentions)
        
        if is_spam:
            await self.handle_spam_violation(message, config, message_count, mention_count)
    
    async def check_swear_filter(self, message: discord.Message, config: dict):
        """Check message against swear filter."""
        swear_config = config.get('swear', {})
        if not swear_config.get('enabled', False):
            return
        
        guild_id = message.guild.id
        
        # Compile patterns if not cached
        if guild_id not in self.swear_patterns:
            swear_list = config.get('swear_list', [])
            allow_list = config.get('allow_list', [])
            
            # Convert wildcard patterns to regex
            patterns = []
            for term in swear_list:
                # Escape special regex characters except *
                escaped = re.escape(term).replace('\\*', '.*')
                patterns.append(f'\\b{escaped}\\b')
            
            allow_patterns = []
            for term in allow_list:
                escaped = re.escape(term).replace('\\*', '.*')
                allow_patterns.append(f'\\b{escaped}\\b')
            
            self.swear_patterns[guild_id] = {
                'swear': re.compile('|'.join(patterns), re.IGNORECASE) if patterns else None,
                'allow': re.compile('|'.join(allow_patterns), re.IGNORECASE) if allow_patterns else None
            }
        
        patterns = self.swear_patterns[guild_id]
        
        # Check for matches
        if patterns['swear']:
            matches = patterns['swear'].findall(message.content)
            if matches:
                # Check if allowed
                if patterns['allow'] and patterns['allow'].search(message.content):
                    return  # Allowed by whitelist
                
                await self.handle_swear_violation(message, config, matches)
    
    async def handle_spam_violation(self, message: discord.Message, config: dict, message_count: int, mention_count: int):
        """Handle spam filter violation."""
        spam_config = config.get('spam', {})
        action = spam_config.get('action', 'delete')
        
        # Delete message if configured
        if action in ['delete', 'warn', 'timeout']:
            try:
                await message.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except discord.Forbidden:
                pass  # No permission to delete
        
        # Create incident record
        async with get_session() as session:
            incident = ModerationIncident(
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                message_id=message.id,
                type="spam",
                reason=f"Spam detected: {message_count} messages, {mention_count} mentions",
                message_snapshot={"content": message.content, "author": str(message.author)},
                action_taken=action
            )
            session.add(incident)
            await session.commit()
        
        # Take additional action
        if action == 'warn':
            try:
                await message.author.send(
                    f"⚠️ **Spam Warning** - {message.guild.name}\n\n"
                    "Your message was detected as spam and has been removed. "
                    "Please avoid sending too many messages quickly or using excessive mentions."
                )
            except discord.Forbidden:
                pass  # User has DMs disabled
        
        elif action == 'timeout':
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
                await message.author.timeout(
                    timeout_until, 
                    reason="Auto-moderation: Spam detected"
                )
                
                try:
                    await message.author.send(
                        f"⏰ **Auto-Timeout** - {message.guild.name}\n\n"
                        "You have been timed out for 10 minutes due to spam detection. "
                        f"Timeout expires: {discord.utils.format_dt(timeout_until)}"
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
            except discord.Forbidden:
                pass  # No permission to timeout
    
    async def handle_swear_violation(self, message: discord.Message, config: dict, matches: List[str]):
        """Handle swear filter violation."""
        swear_config = config.get('swear', {})
        action = swear_config.get('action', 'warn')
        delete_on_match = swear_config.get('delete_on_match', True)
        
        # Delete message if configured
        if delete_on_match:
            try:
                await message.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except discord.Forbidden:
                pass  # No permission to delete
        
        # Create incident record
        async with get_session() as session:
            incident = ModerationIncident(
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                message_id=message.id,
                type="swear",
                reason=f"Inappropriate language detected: {', '.join(matches)}",
                message_snapshot={"content": message.content, "author": str(message.author)},
                action_taken=action
            )
            session.add(incident)
            await session.commit()
        
        # Take action based on configuration
        if action == 'warn':
            try:
                await message.author.send(
                    f"⚠️ **Language Warning** - {message.guild.name}\n\n"
                    "Your message contained inappropriate language and has been removed. "
                    "Please be mindful of the server rules regarding language."
                )
            except discord.Forbidden:
                pass  # User has DMs disabled
        
        elif action == 'timeout':
            timeout_duration = swear_config.get('timeout_duration_minutes', 10)
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=timeout_duration)
                await message.author.timeout(
                    timeout_until,
                    reason="Auto-moderation: Inappropriate language"
                )
                
                try:
                    await message.author.send(
                        f"⏰ **Auto-Timeout** - {message.guild.name}\n\n"
                        f"You have been timed out for {timeout_duration} minutes due to inappropriate language. "
                        f"Timeout expires: {discord.utils.format_dt(timeout_until)}"
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
            except discord.Forbidden:
                pass  # No permission to timeout
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Clean up data when bot leaves a guild."""
        # Clean up spam tracker
        if guild.id in self.spam_tracker:
            del self.spam_tracker[guild.id]
        
        # Clean up swear patterns
        if guild.id in self.swear_patterns:
            del self.swear_patterns[guild.id]


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))