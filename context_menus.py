"""
Context menu commands for the Guild Management Bot
"""

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from database import User, Character, get_session, ModerationLog
from utils.permissions import PermissionChecker


class ContextMenus(commands.Cog):
    """Context menu commands for enhanced user experience."""

    def __init__(self, bot):
        self.bot = bot

        # Add context menus
        self.ctx_create_poll_from_message = app_commands.ContextMenu(
            name='Create Poll from Message',
            callback=self.create_poll_from_message,
        )
        self.bot.tree.add_command(self.ctx_create_poll_from_message)

        self.ctx_moderate_message = app_commands.ContextMenu(
            name='Moderate Message',
            callback=self.moderate_message,
        )
        self.bot.tree.add_command(self.ctx_moderate_message)

        self.ctx_manage_user_roles = app_commands.ContextMenu(
            name='Manage Roles',
            callback=self.manage_user_roles,
        )
        self.bot.tree.add_command(self.ctx_manage_user_roles)

        self.ctx_view_user_profile = app_commands.ContextMenu(
            name='View Profile',
            callback=self.view_user_profile,
        )
        self.bot.tree.add_command(self.ctx_view_user_profile)

    @staticmethod
    async def create_poll_from_message(interaction: discord.Interaction, message: discord.Message):
        """Create a poll using the selected message as the question."""
        # Check if user can create polls
        bot = interaction.client
        config_cache = getattr(bot, 'config_cache', None)

        if config_cache:
            poll_config = await config_cache.get_poll_config(interaction.guild_id)
            creator_roles = poll_config.get('creator_roles', [])

            if not PermissionChecker.can_create_polls(interaction.user, creator_roles):
                embed = PermissionChecker.get_permission_error_embed(
                    "create polls",
                    "Administrator, Manage Server, Manage Roles, or designated poll creator role"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        elif not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Use message content as poll question
        question = message.content[:200] + "..." if len(message.content) > 200 else message.content

        if not question.strip():
            embed = discord.Embed(
                title="❌ No Content",
                description="The selected message has no text content to use as a poll question.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        from views.polls import PollOptionsModal
        modal = PollOptionsModal(question)
        await interaction.response.send_modal(modal)

    @staticmethod
    async def moderate_message(interaction: discord.Interaction, message: discord.Message):
        """Open moderation interface for the selected message."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "moderate messages",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = MessageModerationView(message)

        embed = discord.Embed(
            title="🛡️ Message Moderation",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Message Info",
            value=(
                f"**Author:** {message.author.mention}\n"
                f"**Channel:** {message.channel.mention}\n"
                f"**Created:** {discord.utils.format_dt(message.created_at, 'R')}"
            ),
            inline=False
        )

        # Show message content (truncated)
        content = message.content if message.content else "*No text content*"
        if len(content) > 500:
            content = content[:500] + "..."

        embed.add_field(
            name="Content",
            value=f"```{content}```",
            inline=False
        )

        if message.attachments:
            embed.add_field(
                name="Attachments",
                value=f"{len(message.attachments)} file(s) attached",
                inline=True
            )

        embed.add_field(
            name="Message Link",
            value=f"[Jump to message]({message.jump_url})",
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @staticmethod
    async def manage_user_roles(interaction: discord.Interaction, member: discord.Member):
        """Open role management interface for the selected user."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage user roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if member.bot:
            embed = discord.Embed(
                title="❌ Cannot Manage Bot",
                description="Role management is not available for bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        from views.moderation import UserRoleManagerView
        view = UserRoleManagerView(member)
        await view.show_interface(interaction)

    @staticmethod
    async def view_user_profile(interaction: discord.Interaction, member: discord.Member):
        """View a user's character profile."""
        if member.bot:
            embed = discord.Embed(
                title="❌ No Profile Available",
                description="Bot accounts don't have character profiles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if user has any characters
        async with get_session() as session:
            # Get user
            user_result = await session.execute(
                select(User).where(User.discord_id == member.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                embed = discord.Embed(
                    title="❌ No Profile Found",
                    description=f"{member.mention} hasn't created any characters yet.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Get user's characters
            chars_result = await session.execute(
                select(Character).where(Character.user_id == user.id)
            )
            characters = chars_result.scalars().all()

            if not characters:
                embed = discord.Embed(
                    title="❌ No Characters Found",
                    description=f"{member.mention} hasn't created any characters yet.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        from views.profiles import UserProfileView
        view = UserProfileView(member.id, characters)
        await view.show_profile(interaction)

    def cog_unload(self):
        """Clean up context menus when cog is unloaded."""
        self.bot.tree.remove_command(self.ctx_create_poll_from_message.name, type=self.ctx_create_poll_from_message.type)
        self.bot.tree.remove_command(self.ctx_moderate_message.name, type=self.ctx_moderate_message.type)
        self.bot.tree.remove_command(self.ctx_manage_user_roles.name, type=self.ctx_manage_user_roles.type)
        self.bot.tree.remove_command(self.ctx_view_user_profile.name, type=self.ctx_view_user_profile.type)


class MessageModerationView(discord.ui.View):
    """View for moderating specific messages."""

    def __init__(self, message: discord.Message):
        super().__init__(timeout=300)
        self.message = message

    @discord.ui.button(label="Delete Message", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def delete_message(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Delete the message."""
        try:
            await self.message.delete()

            embed = discord.Embed(
                title="✅ Message Deleted",
                description="The message has been deleted successfully.",
                color=discord.Color.green()
            )

            # Log action
            bot = interaction.client
            await bot.log_action(
                interaction.guild_id,
                "Message Deletion",
                interaction.user,
                self.message.author,
                f"Deleted message in {self.message.channel.mention}"
            )

        except discord.NotFound:
            embed = discord.Embed(
                title="❌ Message Not Found",
                description="The message has already been deleted or cannot be found.",
                color=discord.Color.red()
            )
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to delete this message.",
                color=discord.Color.red()
            )
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to delete message: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Warn User", style=discord.ButtonStyle.secondary, emoji="⚠️") # type: ignore[arg-type]
    async def warn_user(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Warn the user who sent the message."""
        embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"{self.message.author.mention} has been warned for their message.",
            color=discord.Color.orange()
        )

        try:
            # Log the warning
            async with get_session() as session:
                log_entry = ModerationLog(
                    guild_id=interaction.guild_id,
                    moderator_id=interaction.user.id,
                    target_user_id=self.message.author.id,
                    action_type="warn",
                    reason="Message content warning",
                    message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                    action_taken="warn"
                )
                session.add(log_entry)
                await session.commit()

            # Try to send a DM to the user
            try:
                dm_embed = discord.Embed(
                    title="⚠️ Warning",
                    description=f"You have been warned in **{interaction.guild.name}** for a message you posted.",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(
                    name="Message",
                    value=f"[Jump to message]({self.message.jump_url})",
                    inline=False
                )
                dm_embed.add_field(
                    name="Reason",
                    value="Message content warning",
                    inline=False
                )
                await self.message.author.send(embed=dm_embed)
                embed.add_field(name="DM Sent", value="✅ User has been notified", inline=False)
            except (discord.Forbidden, discord.HTTPException):
                embed.add_field(name="DM Failed", value="❌ Could not send DM to user", inline=False)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to warn user: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Timeout User", style=discord.ButtonStyle.danger, emoji="⏰") # type: ignore[arg-type]
    async def timeout_user(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Open timeout options for the user."""
        view = TimeoutDurationView(self.message)

        embed = discord.Embed(
            title="⏰ Timeout User",
            description=f"Select timeout duration for {self.message.author.mention}:",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=view)


class TimeoutDurationView(discord.ui.View):
    """View for selecting timeout duration."""

    def __init__(self, message: discord.Message):
        super().__init__(timeout=300)
        self.message = message
        self.duration_minutes = 10  # Default 10 minutes

    @discord.ui.select(
        placeholder="Select timeout duration...",
        options=[
            discord.SelectOption(label="5 minutes", value="5", emoji="⏰"),
            discord.SelectOption(label="10 minutes", value="10", emoji="⏰", default=True),
            discord.SelectOption(label="30 minutes", value="30", emoji="⏰"),
            discord.SelectOption(label="1 hour", value="60", emoji="⏰"),
            discord.SelectOption(label="6 hours", value="360", emoji="⏰"),
            discord.SelectOption(label="24 hours", value="1440", emoji="⏰"),
        ]
    )
    async def select_duration(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle duration selection."""
        self.duration_minutes = int(select.values[0])

        embed = discord.Embed(
            title="⏰ Confirm Timeout",
            description=f"Timeout {self.message.author.mention} for **{self.duration_minutes} minutes**?",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Confirm Timeout", style=discord.ButtonStyle.danger, emoji="✅") # type: ignore[arg-type]
    async def confirm_timeout(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Execute the timeout."""
        from datetime import datetime, timedelta

        try:
            timeout_until = datetime.now() + timedelta(minutes=self.duration_minutes)
            await self.message.author.timeout(timeout_until, reason="Message moderation timeout")

            embed = discord.Embed(
                title="✅ User Timed Out",
                description=f"{self.message.author.mention} has been timed out for {self.duration_minutes} minutes.",
                color=discord.Color.green()
            )

            # Log the action
            async with get_session() as session:
                log_entry = ModerationLog(
                    guild_id=interaction.guild_id,
                    moderator_id=interaction.user.id,
                    target_user_id=self.message.author.id,
                    action_type="timeout",
                    reason=f"Message timeout - {self.duration_minutes}m",
                    message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                    action_taken=f"timeout_{self.duration_minutes}m"
                )
                session.add(log_entry)
                await session.commit()

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to timeout this user.",
                color=discord.Color.red()
            )
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to timeout user: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌") # type: ignore[arg-type]
    async def cancel_timeout(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Cancel the timeout operation."""
        embed = discord.Embed(
            title="❌ Cancelled",
            description="Timeout operation has been cancelled.",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=None)


def setup(bot):
    bot.add_cog(ContextMenus(bot))