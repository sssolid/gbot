"""
Context menu commands for the Guild Management Bot - FIXED VERSION
"""
import discord
from discord.ext import commands
from sqlalchemy import select

from database import ModerationLog, get_session  # FIXED: Import ModerationLog
from views.polls import PollBuilderModal
from views.moderation import UserRoleManagerView  # FIXED: Import UserRoleManagerView
from utils.permissions import PermissionChecker


class MessageModerationView(discord.ui.View):
    """View for moderating messages via context menu."""

    def __init__(self, message: discord.Message):
        super().__init__(timeout=300)
        self.message = message

    @discord.ui.button(label="Delete Message", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def delete_message(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Delete the reported message."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "delete messages",
                "Administrator, Manage Server, Manage Roles, or Manage Messages"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Try to delete the message
            await self.message.delete()

            # Log the action
            async with get_session() as session:
                log_entry = ModerationLog(
                    guild_id=interaction.guild_id,
                    moderator_id=interaction.user.id,
                    target_user_id=self.message.author.id,
                    action_type="delete_message",
                    reason="Message deleted via context menu",
                    message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                    action_taken="message_deleted"
                )
                session.add(log_entry)
                await session.commit()

            embed = discord.Embed(
                title="🗑️ Message Deleted",
                description="The message has been deleted successfully.",
                color=discord.Color.green()
            )
        except discord.NotFound:
            embed = discord.Embed(
                title="❌ Message Not Found",
                description="The message may have already been deleted.",
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
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "warn users",
                "Administrator, Manage Server, Manage Roles, or Manage Messages"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

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
                    action_taken="user_warned"
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
                    name="Message Content",
                    value=self.message.content[:500] + ("..." if len(self.message.content) > 500 else ""),
                    inline=False
                )
                dm_embed.add_field(
                    name="Moderator",
                    value=interaction.user.display_name,
                    inline=True
                )
                await self.message.author.send(embed=dm_embed)
                embed.add_field(name="DM Sent", value="User has been notified via direct message.", inline=False)
            except (discord.Forbidden, discord.HTTPException):
                embed.add_field(name="DM Failed", value="Could not send direct message to user.", inline=False)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to warn user: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Timeout User", style=discord.ButtonStyle.secondary, emoji="⏰") # type: ignore[arg-type]
    async def timeout_user(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """Timeout the user who sent the message."""
        if not PermissionChecker.has_permission(interaction.user, "moderate_members"):
            embed = PermissionChecker.get_permission_error_embed(
                "timeout users",
                "Administrator, Manage Server, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Timeout for 10 minutes
            import datetime
            from datetime import timezone
            timeout_until = discord.utils.utcnow() + datetime.timedelta(minutes=10)

            await self.message.author.timeout(timeout_until, reason=f"Message timeout by {interaction.user}")

            # Log the action
            async with get_session() as session:
                log_entry = ModerationLog(
                    guild_id=interaction.guild_id,
                    moderator_id=interaction.user.id,
                    target_user_id=self.message.author.id,
                    action_type="timeout",
                    reason="Message content timeout",
                    duration=10,  # 10 minutes
                    message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                    action_taken="user_timeout_10min"
                )
                session.add(log_entry)
                await session.commit()

            embed = discord.Embed(
                title="⏰ User Timed Out",
                description=f"{self.message.author.mention} has been timed out for 10 minutes.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Duration",
                value="10 minutes",
                inline=True
            )
            embed.add_field(
                name="Reason",
                value="Message content violation",
                inline=True
            )

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


class ModerateMessage(commands.Cog):
    """Context menu command for message moderation."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.context_menu(name="Moderate Message")
    async def moderate_message(self, interaction: discord.Interaction, message: discord.Message):
        """Moderate a message via context menu."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "moderate messages",
                "Administrator, Manage Server, Manage Roles, or Manage Messages"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if message.author.bot:
            embed = discord.Embed(
                title="❌ Cannot Moderate Bots",
                description="Bot messages cannot be moderated through this system.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="🛡️ Message Moderation",
            description="Choose an action for this message:",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Message Author",
            value=message.author.mention,
            inline=True
        )

        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=True
        )

        embed.add_field(
            name="Message Content",
            value=message.content[:500] + ("..." if len(message.content) > 500 else ""),
            inline=False
        )

        view = MessageModerationView(message)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CreatePollFromMessage(commands.Cog):
    """Context menu command for creating polls from messages."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.context_menu(name="Create Poll from Message")
    async def create_poll_from_message(self, interaction: discord.Interaction, message: discord.Message):
        """Create a poll based on a message."""
        # Check if user can create polls
        try:
            from utils.cache import get_config
            config = await get_config(self.bot, interaction.guild_id, "poll_permissions", {})
            allowed_roles = config.get("creator_roles", [])

            if allowed_roles:
                user_roles = [role.id for role in interaction.user.roles]
                if not any(role_id in user_roles for role_id in allowed_roles):
                    embed = discord.Embed(
                        title="❌ Permission Denied",
                        description="You don't have permission to create polls.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
        except (AttributeError, TypeError):
            # If config check fails, allow all users
            pass

        # Extract potential poll question from message
        content = message.content.strip()
        if len(content) > 500:
            content = content[:497] + "..."

        # Create a pre-filled poll modal
        modal = PollBuilderModal()
        if content:
            modal.question_input.default = content

        await interaction.response.send_modal(modal)


class ManageUserRoles(commands.Cog):
    """Context menu command for managing user roles."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.context_menu(name="Manage User Roles")
    async def manage_user_roles(self, interaction: discord.Interaction, member: discord.Member):
        """Manage roles for a user via context menu."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if member.bot:
            embed = discord.Embed(
                title="❌ Cannot Manage Bot Roles",
                description="Bot roles cannot be managed through this system.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if target user is higher in hierarchy
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            embed = discord.Embed(
                title="❌ Insufficient Permissions",
                description="You cannot manage roles for users with equal or higher roles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # FIXED: Use the imported UserRoleManagerView
        view = UserRoleManagerView(member)
        await view.show_role_manager(interaction)


class ViewUserProfile(commands.Cog):
    """Context menu command for viewing user profiles."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.context_menu(name="View Character Profile")
    async def view_character_profile(self, interaction: discord.Interaction, member: discord.Member):
        """View a user's character profile via context menu."""
        if member.bot:
            embed = discord.Embed(
                title="❌ No Profile Available",
                description="Bots don't have character profiles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        from views.profiles import CharacterViewerView
        viewer = CharacterViewerView(member.id)
        await viewer.show_character_profile(interaction)


async def setup(bot):
    """Setup function for context menu cogs."""
    await bot.add_cog(ModerateMessage(bot))
    await bot.add_cog(CreatePollFromMessage(bot))
    await bot.add_cog(ManageUserRoles(bot))
    await bot.add_cog(ViewUserProfile(bot))