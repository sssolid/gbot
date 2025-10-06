# File: cogs/moderation_utils.py
# Location: /bot/cogs/moderation_utils.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging

from models import (
    Guild, Member, Submission, RoleTier, ApplicationStatus,
    ModeratorAction, ActionType, RateLimitLog
)
from database import db
from utils.helpers import create_embed, try_send_dm, get_role_id

logger = logging.getLogger(__name__)


class ModerationUtilsCog(commands.Cog):
    """Advanced moderation utilities"""

    def __init__(self, bot):
        self.bot = bot

    async def check_rate_limit(self, user_id: int, command: str, max_uses: int = 5, window_minutes: int = 5) -> bool:
        """Check if user is rate limited"""
        with db.session_scope() as session:
            cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

            recent_uses = session.query(RateLimitLog).filter(
                RateLimitLog.user_id == user_id,
                RateLimitLog.command == command,
                RateLimitLog.timestamp >= cutoff
            ).count()

            if recent_uses >= max_uses:
                return True

            # Log this use
            log = RateLimitLog(
                user_id=user_id,
                command=command
            )
            session.add(log)

        return False

    @app_commands.command(name="admin_reset_user", description="Reset a user's onboarding process")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="The member to reset")
    async def admin_reset_user(self, interaction: discord.Interaction, member: discord.Member):
        """Moderator command to reset user onboarding"""
        if not await self._check_moderator(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            member_record = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=member.id
            ).first()

            if not member_record:
                await interaction.response.send_message("❌ Member record not found.", ephemeral=True)
                return

            # Delete all submissions
            submissions = session.query(Submission).filter_by(member_id=member_record.id).all()
            for sub in submissions:
                session.delete(sub)

            # Reset status
            old_status = member_record.status
            old_tier = member_record.role_tier

            member_record.status = ApplicationStatus.IN_PROGRESS
            member_record.role_tier = None

            # Log action
            action = ModeratorAction(
                target_user_id=member.id,
                moderator_id=interaction.user.id,
                action_type=ActionType.RESET,
                reason=f"Reset by {interaction.user.name}"
            )
            session.add(action)

            session.commit()

        # Remove Discord roles
        if old_tier:
            role_id = await get_role_id(interaction.guild.id, old_tier)
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason=f"Reset by {interaction.user.name}")
                    except discord.Forbidden:
                        logger.error(f"Cannot remove role from {member.id}")

        # Send DM to user
        embed = await create_embed(
            title="🔄 Onboarding Reset",
            description=(
                f"A moderator has reset your onboarding process in **{interaction.guild.name}**.\n\n"
                "You can now restart the application process. Use `/apply` or `/reset` in the server."
            ),
            color=discord.Color.blue()
        )
        await try_send_dm(member, embed=embed)

        await interaction.response.send_message(
            f"✅ Reset onboarding for {member.mention}. User has been notified.",
            ephemeral=True
        )

    @app_commands.command(name="admin_strip_roles", description="Strip all roles from a user and reset their status")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to reset",
        reason="Reason for stripping roles"
    )
    async def admin_strip_roles(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = None
    ):
        """Strip all roles from user and reset status"""
        if not await self._check_moderator(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            member_record = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=member.id
            ).first()

            if not member_record:
                await interaction.response.send_message("❌ Member record not found.", ephemeral=True)
                return

            # Delete all submissions
            submissions = session.query(Submission).filter_by(member_id=member_record.id).all()
            for sub in submissions:
                session.delete(sub)

            old_tier = member_record.role_tier
            member_record.status = ApplicationStatus.IN_PROGRESS
            member_record.role_tier = None

            # Log action
            action = ModeratorAction(
                target_user_id=member.id,
                moderator_id=interaction.user.id,
                action_type=ActionType.STRIP_ROLES,
                reason=reason or f"Roles stripped by {interaction.user.name}"
            )
            session.add(action)

            session.commit()

        # Remove all guild roles from Discord
        roles_to_remove = [r for r in member.roles if r != interaction.guild.default_role and not r.managed]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=reason or "Roles stripped by moderator")
            except discord.Forbidden:
                logger.error(f"Cannot remove roles from {member.id}")

        # Send DM to user
        embed = await create_embed(
            title="⚠️ Status Reset",
            description=(
                f"Your status in **{interaction.guild.name}** has been reset by a moderator.\n\n"
                f"{f'**Reason:** {reason}' if reason else ''}\n\n"
                "All your roles have been removed. You can restart the onboarding process using `/reset` in the server."
            ),
            color=discord.Color.orange()
        )
        await try_send_dm(member, embed=embed)

        await interaction.response.send_message(
            f"✅ Stripped all roles from {member.mention} and reset their status. User has been notified.",
            ephemeral=True
        )

    @app_commands.command(name="admin_dm", description="Send a DM to a user through the bot")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="The member to message")
    async def admin_dm(self, interaction: discord.Interaction, member: discord.Member):
        """Send DM to user through bot"""
        if not await self._check_moderator(interaction):
            return

        modal = DMUserModal(self.bot, member)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="admin_send", description="Send a message to a channel through the bot")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(channel="The channel to send to")
    async def admin_send(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Send message to channel through bot"""
        if not await self._check_moderator(interaction):
            return

        modal = SendChannelModal(self.bot, channel)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="view_logs", description="View message logs for a user")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to view logs for",
        limit="Number of messages to show (default 10)"
    )
    async def view_logs(self, interaction: discord.Interaction, member: discord.Member, limit: int = 10):
        """View message logs for a user"""
        if not await self._check_moderator(interaction):
            return

        from models import MessageLog

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            logs = session.query(MessageLog).filter_by(
                guild_id=guild.id,
                user_id=member.id
            ).order_by(MessageLog.timestamp.desc()).limit(limit).all()

            if not logs:
                await interaction.response.send_message(
                    f"📭 No message logs found for {member.mention}",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"📜 Message Logs - {member.display_name}",
                description=f"Showing last {len(logs)} messages",
                color=discord.Color.blue()
            )

            for log in logs:
                channel = interaction.guild.get_channel(log.channel_id)
                channel_name = channel.name if channel else f"Channel {log.channel_id}"

                status = ""
                if log.deleted:
                    status = " ❌ [DELETED]"
                elif log.edited:
                    status = " ✏️ [EDITED]"

                content = log.content[:100] if log.content else "[No content]"
                timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M UTC")

                embed.add_field(
                    name=f"#{channel_name} - {timestamp}{status}",
                    value=f"```{content}```",
                    inline=False
                )

            embed.set_footer(text=f"User ID: {member.id}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="search_logs", description="Search deleted messages")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        query="Search term",
        member="Optional: Filter by member"
    )
    async def search_logs(
            self,
            interaction: discord.Interaction,
            query: str,
            member: discord.Member = None
    ):
        """Search message logs"""
        if not await self._check_moderator(interaction):
            return

        from models import MessageLog

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            query_filter = MessageLog.guild_id == guild.id
            query_filter &= MessageLog.content.ilike(f"%{query}%")

            if member:
                query_filter &= MessageLog.user_id == member.id

            logs = session.query(MessageLog).filter(query_filter).order_by(
                MessageLog.timestamp.desc()
            ).limit(10).all()

            if not logs:
                await interaction.response.send_message(
                    f"📭 No messages found matching '{query}'",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🔍 Search Results - '{query}'",
                description=f"Found {len(logs)} messages",
                color=discord.Color.blue()
            )

            for log in logs:
                channel = interaction.guild.get_channel(log.channel_id)
                channel_name = channel.name if channel else f"Channel {log.channel_id}"

                status = ""
                if log.deleted:
                    status = " ❌ [DELETED]"
                elif log.edited:
                    status = " ✏️ [EDITED]"

                content = log.content[:200] if log.content else "[No content]"
                timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M UTC")

                embed.add_field(
                    name=f"<@{log.user_id}> in #{channel_name} - {timestamp}{status}",
                    value=f"```{content}```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    # Context menu commands
    async def reset_user_context(self, interaction: discord.Interaction, member: discord.Member):
        """Context menu: Reset user onboarding"""
        await self.admin_reset_user.callback(self, interaction, member)

    async def strip_roles_context(self, interaction: discord.Interaction, member: discord.Member):
        """Context menu: Strip all roles"""
        # Show modal for reason
        modal = StripRolesReasonModal(self, member)
        await interaction.response.send_modal(modal)

    async def dm_user_context(self, interaction: discord.Interaction, member: discord.Member):
        """Context menu: DM user"""
        await self.admin_dm.callback(self, interaction, member)

    async def view_logs_context(self, interaction: discord.Interaction, member: discord.Member):
        """Context menu: View logs"""
        await self.view_logs.callback(self, interaction, member)

    async def _check_moderator(self, interaction: discord.Interaction) -> bool:
        """Check if user has moderator permissions"""
        from utils.checks import is_moderator
        if not await is_moderator(interaction):
            await interaction.response.send_message(
                "❌ You need moderator permissions to use this command.",
                ephemeral=True
            )
            return False
        return True


class DMUserModal(discord.ui.Modal):
    """Modal for sending DM through bot"""

    def __init__(self, bot, member: discord.Member):
        super().__init__(title=f"DM {member.display_name}")
        self.bot = bot
        self.member = member

        self.message = discord.ui.TextInput(
            label="Message",
            placeholder="Enter message to send...",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        embed = await create_embed(
            title=f"Message from {interaction.guild.name} Moderators",
            description=self.message.value,
            color=discord.Color.blue(),
            footer=f"Sent by {interaction.user.name}"
        )

        success = await try_send_dm(self.member, embed=embed)

        if success:
            await interaction.response.send_message(
                f"✅ Message sent to {self.member.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Could not send message to {self.member.mention}. They may have DMs disabled.",
                ephemeral=True
            )


class SendChannelModal(discord.ui.Modal):
    """Modal for sending message to channel"""

    def __init__(self, bot, channel: discord.TextChannel):
        super().__init__(title=f"Send to #{channel.name}")
        self.bot = bot
        self.channel = channel

        self.title_input = discord.ui.TextInput(
            label="Title (optional)",
            placeholder="Message title...",
            style=discord.TextStyle.short,
            required=False,
            max_length=256
        )
        self.add_item(self.title_input)

        self.message = discord.ui.TextInput(
            label="Message",
            placeholder="Enter message content...",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.title_input.value:
                embed = discord.Embed(
                    title=self.title_input.value,
                    description=self.message.value,
                    color=discord.Color.blue()
                )
                await self.channel.send(embed=embed)
            else:
                await self.channel.send(self.message.value)

            await interaction.response.send_message(
                f"✅ Message sent to {self.channel.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {self.channel.mention}",
                ephemeral=True
            )


class StripRolesReasonModal(discord.ui.Modal):
    """Modal for strip roles reason"""

    def __init__(self, cog, member: discord.Member):
        super().__init__(title=f"Strip Roles - {member.display_name}")
        self.cog = cog
        self.member = member

        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter reason for stripping roles...",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.admin_strip_roles.callback(
            self.cog,
            interaction,
            self.member,
            self.reason.value
        )


async def setup(bot):
    cog = ModerationUtilsCog(bot)
    await bot.add_cog(cog)

    # Create context menus pointing to cog methods
    reset_menu = app_commands.ContextMenu(
        name="Reset User",
        callback=cog.reset_user_context,
    )
    strip_menu = app_commands.ContextMenu(
        name="Strip Roles",
        callback=cog.strip_roles_context,
    )
    dm_menu = app_commands.ContextMenu(
        name="DM User",
        callback=cog.dm_user_context,
    )
    logs_menu = app_commands.ContextMenu(
        name="View User Logs",
        callback=cog.view_logs_context,
    )

    # Set permissions (like your decorators did)
    reset_menu.default_permissions = discord.Permissions(moderate_members=True)
    strip_menu.default_permissions = discord.Permissions(manage_roles=True)
    dm_menu.default_permissions = discord.Permissions(moderate_members=True)
    logs_menu.default_permissions = discord.Permissions(moderate_members=True)

    # Register them
    bot.tree.add_command(reset_menu)
    bot.tree.add_command(strip_menu)
    bot.tree.add_command(dm_menu)
    bot.tree.add_command(logs_menu)