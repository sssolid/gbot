"""
Moderation cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import datetime, timedelta
import re

from database import ModerationIncident, get_session
from utils.permissions import PermissionChecker
from views.moderation import ModerationCenterView, ReportModal


class ModerationCog(commands.Cog):
    """Handles moderation commands and auto-moderation."""
    
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = {}  # Track message counts per user per channel
        self.swear_patterns = {}  # Compiled regex patterns per guild
    
    @app_commands.command(name="moderation", description="Open moderation center (Moderator only)")
    async def moderation_center(self, interaction: discord.Interaction):
        """Open the moderation center."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access moderation center",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = ModerationCenterView()
        
        embed = discord.Embed(
            title="🛡️ Moderation Center",
            description="Configure and manage server moderation settings.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="warn", description="Warn a user (Moderator only)")
    @app_commands.describe(
        user="User to warn",
        reason="Reason for the warning"
    )
    async def warn_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        """Warn a user."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "warn users",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if user.bot:
            embed = discord.Embed(
                title="❌ Cannot Warn Bot",
                description="You cannot warn bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Send warning DM
        dm_status = "✅ DM sent"
        try:
            warning_embed = discord.Embed(
                title=f"⚠️ Warning - {interaction.guild.name}",
                description="You have received a warning from our moderation team.",
                color=discord.Color.orange()
            )
            warning_embed.add_field(name="Reason", value=reason, inline=False)
            warning_embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            warning_embed.set_footer(text="Please review our server rules to avoid future warnings.")
            
            await user.send(embed=warning_embed)
        except discord.Forbidden:
            dm_status = "❌ DM failed (user has DMs disabled)"
        
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
        
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"Warning sent to {user.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="DM Status", value=dm_status, inline=True)
        
        # Log action
        await self.bot.log_action(
            interaction.guild_id,
            "User Warning",
            interaction.user,
            user,
            f"Reason: {reason}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="timeout", description="Timeout a user (Moderator only)")
    @app_commands.describe(
        user="User to timeout",
        duration="Duration in minutes",
        reason="Reason for the timeout"
    )
    async def timeout_user(self, interaction: discord.Interaction, user: discord.Member, duration: int, reason: str):
        """Timeout a user."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "timeout users",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if user.bot:
            embed = discord.Embed(
                title="❌ Cannot Timeout Bot",
                description="You cannot timeout bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if duration <= 0 or duration > 40320:  # Discord's max timeout is 28 days = 40320 minutes
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description="Timeout duration must be between 1 minute and 28 days (40320 minutes).",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Apply timeout
        timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
        
        try:
            await user.timeout(timeout_until, reason=f"{reason} (by {interaction.user})")
            
            # Format duration
            if duration < 60:
                duration_text = f"{duration} minute(s)"
            else:
                hours = duration // 60
                minutes = duration % 60
                duration_text = f"{hours} hour(s)"
                if minutes > 0:
                    duration_text += f" and {minutes} minute(s)"
            
            # Create incident record
            async with get_session() as session:
                incident = ModerationIncident(
                    guild_id=interaction.guild_id,
                    user_id=user.id,
                    channel_id=interaction.channel_id,
                    type="manual_timeout",
                    reason=reason,
                    action_taken=f"timeout_{duration}m",
                    moderator_id=interaction.user.id
                )
                session.add(incident)
                await session.commit()
            
            embed = discord.Embed(
                title="⏰ User Timed Out",
                description=f"{user.mention} has been timed out for {duration_text}.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Until", value=discord.utils.format_dt(timeout_until, 'F'), inline=True)
            
            # Log action
            await self.bot.log_action(
                interaction.guild_id,
                "User Timeout",
                interaction.user,
                user,
                f"Duration: {duration_text}, Reason: {reason}"
            )
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to timeout this user.",
                color=discord.Color.red()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to timeout user: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="incidents", description="View recent moderation incidents (Moderator only)")
    @app_commands.describe(
        user="Filter by specific user",
        incident_type="Filter by incident type",
        limit="Number of incidents to show"
    )
    @app_commands.choices(incident_type=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Spam", value="spam"),
        app_commands.Choice(name="Swear Filter", value="swear"),
        app_commands.Choice(name="Manual Reports", value="manual_report"),
        app_commands.Choice(name="Warnings", value="manual_warn"),
        app_commands.Choice(name="Timeouts", value="manual_timeout")
    ])
    async def view_incidents(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        incident_type: str = "all",
        limit: int = 10
    ):
        """View recent moderation incidents."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view moderation incidents",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if limit > 25:
            limit = 25  # Discord embed limit
        
        async with get_session() as session:
            query = select(ModerationIncident).where(ModerationIncident.guild_id == interaction.guild_id)
            
            if user:
                query = query.where(ModerationIncident.user_id == user.id)
            
            if incident_type != "all":
                query = query.where(ModerationIncident.type == incident_type)
            
            result = await session.execute(
                query.order_by(ModerationIncident.created_at.desc()).limit(limit)
            )
            incidents = result.scalars().all()
        
        if not incidents:
            filter_text = ""
            if user:
                filter_text += f" for {user.display_name}"
            if incident_type != "all":
                filter_text += f" ({incident_type})"
            
            embed = discord.Embed(
                title="📋 Moderation Incidents",
                description=f"No incidents found{filter_text}.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        title = "📋 Recent Moderation Incidents"
        if user:
            title += f" - {user.display_name}"
        if incident_type != "all":
            title += f" ({incident_type.title()})"
        
        embed = discord.Embed(
            title=title,
            description=f"Showing {len(incidents)} recent incident(s).",
            color=discord.Color.orange()
        )
        
        for incident in incidents:
            target_user = interaction.guild.get_member(incident.user_id)
            target_name = target_user.display_name if target_user else f"User {incident.user_id}"
            
            moderator = interaction.guild.get_member(incident.moderator_id) if incident.moderator_id else None
            moderator_name = moderator.display_name if moderator else "System"
            
            channel = interaction.guild.get_channel(incident.channel_id)
            channel_name = channel.mention if channel else f"Channel {incident.channel_id}"
            
            embed.add_field(
                name=f"{incident.type.replace('_', ' ').title()} - {discord.utils.format_dt(incident.created_at, 'R')}",
                value=(
                    f"**User:** {target_name}\n"
                    f"**Channel:** {channel_name}\n"
                    f"**Action:** {incident.action_taken or 'None'}\n"
                    f"**Moderator:** {moderator_name}\n"
                    f"**Reason:** {incident.reason[:100] if incident.reason else 'No reason provided'}{'...' if incident.reason and len(incident.reason) > 100 else ''}"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"Guild ID: {interaction.guild_id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="report", description="Report inappropriate content")
    async def report_content(self, interaction: discord.Interaction):
        """Open content reporting interface."""
        modal = ReportModal()
        await interaction.response.send_modal(modal)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle message for auto-moderation."""
        if message.author.bot or not message.guild:
            return
        
        # Get moderation config
        config_cache = getattr(self.bot, 'config_cache', None)
        if not config_cache:
            return
        
        moderation_config = await config_cache.get_moderation_config(message.guild.id)
        
        # Check if channel is watched
        watch_channels = moderation_config.get('watch_channels', [])
        if watch_channels and message.channel.id not in watch_channels:
            return
        
        # Check staff exemptions
        staff_roles = moderation_config.get('staff_roles', [])
        if staff_roles and PermissionChecker.has_role(message.author, staff_roles):
            return
        
        # Check spam filter
        await self.check_spam_filter(message, moderation_config)
        
        # Check swear filter
        await self.check_swear_filter(message, moderation_config)
    
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
            swear_list = swear_config.get('swear_list', [])
            allow_list = swear_config.get('allow_list', [])
            
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
                pass
        elif action == 'timeout':
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=5)
                await message.author.timeout(timeout_until, reason="Spam detection")
            except discord.Forbidden:
                pass
    
    async def handle_swear_violation(self, message: discord.Message, config: dict, matches: List[str]):
        """Handle swear filter violation."""
        swear_config = config.get('swear', {})
        delete_on_match = swear_config.get('delete_on_match', True)
        action = swear_config.get('action', 'warn')
        
        # Delete message if configured
        if delete_on_match:
            try:
                await message.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
        
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
        
        # Take action
        if action == 'warn':
            try:
                await message.author.send(
                    f"⚠️ **Language Warning** - {message.guild.name}\n\n"
                    "Your message contained inappropriate language and has been removed. "
                    "Please review the server rules and keep your language appropriate."
                )
            except discord.Forbidden:
                pass
        elif action == 'timeout':
            timeout_duration = swear_config.get('timeout_duration_minutes', 10)
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=timeout_duration)
                await message.author.timeout(timeout_until, reason="Inappropriate language")
            except discord.Forbidden:
                pass


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ModerationCog(bot))