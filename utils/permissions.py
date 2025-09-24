"""
Permission checking utilities for the Guild Management Bot
"""
from functools import wraps
import discord
from typing import Union, List, Optional


class PermissionChecker:
    """Handles permission checking for bot operations."""

    @staticmethod
    def is_admin(member: discord.Member) -> bool:
        """Check if a member has admin permissions."""
        return (
            member.guild_permissions.administrator or
            member.guild_permissions.manage_guild or
            member.guild_permissions.manage_roles
        )

    @staticmethod
    def is_moderator(member: discord.Member) -> bool:
        """Check if a member has moderator permissions."""
        return (
            PermissionChecker.is_admin(member) or
            member.guild_permissions.manage_messages or
            member.guild_permissions.moderate_members
        )

    @staticmethod
    def can_manage_roles(member: discord.Member, bot_member: discord.Member) -> bool:
        """Check if a member can manage roles and if the bot can too."""
        return (
            PermissionChecker.is_admin(member) and
            bot_member.guild_permissions.manage_roles
        )

    @staticmethod
    def can_assign_role(bot_member: discord.Member, role: discord.Role) -> bool:
        """Check if the bot can assign a specific role."""
        return (
            bot_member.guild_permissions.manage_roles and
            bot_member.top_role > role
        )

    @staticmethod
    def has_role(member: discord.Member, role_ids: Union[int, List[int]]) -> bool:
        """Check if a member has any of the specified roles."""
        if isinstance(role_ids, int):
            role_ids = [role_ids]

        member_role_ids = {role.id for role in member.roles}
        return any(role_id in member_role_ids for role_id in role_ids)

    @staticmethod
    def can_create_polls(member: discord.Member, poll_creator_roles: Optional[List[int]] = None) -> bool:
        """Check if a member can create polls."""
        if PermissionChecker.is_admin(member):
            return True

        if poll_creator_roles:
            return PermissionChecker.has_role(member, poll_creator_roles)

        return False

    @staticmethod
    def get_permission_error_embed(action: str, required_permissions: str) -> discord.Embed:
        """Get a standardized permission error embed."""
        embed = discord.Embed(
            title="❌ Insufficient Permissions",
            description=f"You don't have permission to {action}.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Required Permissions",
            value=required_permissions,
            inline=False
        )
        return embed

    @staticmethod
    def get_bot_permission_error_embed(action: str, required_permissions: str) -> discord.Embed:
        """Get a standardized bot permission error embed."""
        embed = discord.Embed(
            title="❌ Bot Missing Permissions",
            description=f"I don't have permission to {action}.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Required Bot Permissions",
            value=required_permissions,
            inline=False
        )
        embed.add_field(
            name="Solution",
            value="Please ensure the bot has the required permissions and that my role is positioned high enough in the role hierarchy.",
            inline=False
        )
        return embed


def require_admin():
    """Decorator to require admin permissions for a view interaction."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not PermissionChecker.is_admin(interaction.user):
                embed = PermissionChecker.get_permission_error_embed(
                    "use this feature",
                    "Administrator, Manage Server, or Manage Roles"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return None
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator

def require_moderator():
    """Decorator to require moderator permissions for a view interaction."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not PermissionChecker.is_moderator(interaction.user):
                embed = PermissionChecker.get_permission_error_embed(
                    "use this feature",
                    "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return None
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator