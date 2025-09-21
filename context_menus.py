"""
Context menu commands for the Guild Management Bot
"""
import discord
from discord import app_commands, InteractionMessage
from discord.ext import commands
from sqlalchemy import select, and_

from database import User, Character, get_session
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
    
    async def create_poll_from_message(self, interaction: discord.Interaction, message: discord.Message):
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
    
    async def moderate_message(self, interaction: discord.Interaction, message: discord.Message):
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
    
    async def manage_user_roles(self, interaction: discord.Interaction, member: discord.Member):
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
        
        embed = discord.Embed(
            title="🎭 Role Management",
            description=f"Managing roles for {member.mention}",
            color=discord.Color.blue()
        )
        
        current_roles = [role for role in member.roles if role != interaction.guild.default_role]
        if current_roles:
            embed.add_field(
                name="Current Roles",
                value="\n".join(role.mention for role in current_roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Current Roles",
                value="No roles assigned",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def view_user_profile(self, interaction: discord.Interaction, member: discord.Member):
        """View user's character profile."""
        if member.bot:
            embed = discord.Embed(
                title="❌ Bot Account",
                description="Profiles are not available for bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Load user's characters
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == member.id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            user = result.scalar_one_or_none()
            
            if not user:
                embed = discord.Embed(
                    title="👤 User Profile",
                    description=f"{member.mention} hasn't created any characters yet.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            result = await session.execute(
                select(Character).where(Character.user_id == user.id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            characters = result.scalars().all()
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Profile",
            color=discord.Color.blue()
        )
        
        if not characters:
            embed.description = "This user hasn't created any characters yet."
        else:
            for char in characters[:5]:  # Show up to 5 characters
                main_indicator = "⭐ " if char.is_main else ""
                archetype_text = f" ({char.archetype})" if char.archetype else ""
                
                value = f"**{main_indicator}{char.name}**{archetype_text}"
                if char.build_notes:
                    value += f"\n*{char.build_notes[:100]}{'...' if len(char.build_notes) > 100 else ''}*"
                
                embed.add_field(
                    name=f"Character {len([f for f in embed.fields]) + 1}",
                    value=value,
                    inline=False
                )
            
            if len(characters) > 5:
                embed.add_field(
                    name="",
                    value=f"*...and {len(characters) - 5} more character(s)*",
                    inline=False
                )
        
        embed.add_field(
            name="Member Since",
            value=discord.utils.format_dt(member.joined_at, 'D') if member.joined_at else "Unknown",
            inline=True
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")
        
        # Add admin actions if user is admin
        if PermissionChecker.is_admin(interaction.user):
            from views.profiles import UserProfileAdminView
            view = UserProfileAdminView(member, characters)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.bot.tree.remove_command(self.ctx_create_poll_from_message.name, type=self.ctx_create_poll_from_message.type)
        self.bot.tree.remove_command(self.ctx_moderate_message.name, type=self.ctx_moderate_message.type)
        self.bot.tree.remove_command(self.ctx_manage_user_roles.name, type=self.ctx_manage_user_roles.type)
        self.bot.tree.remove_command(self.ctx_view_user_profile.name, type=self.ctx_view_user_profile.type)


class MessageModerationView(discord.ui.View):
    """View for moderating specific messages."""
    
    def __init__(self, message: discord.Message):
        super().__init__(timeout=300)
        self.message = message
    
    @discord.ui.button(label="Delete Message", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to delete message: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Warn User", style=discord.ButtonStyle.secondary, emoji="⚠️")
    async def warn_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Warn the user who sent the message."""
        modal = WarnUserModal(self.message)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Timeout User", style=discord.ButtonStyle.secondary, emoji="⏰")
    async def timeout_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Timeout the user who sent the message."""
        view = TimeoutUserView(self.message)
        
        embed = discord.Embed(
            title="⏰ Timeout User",
            description=f"Select timeout duration for {self.message.author.mention}:",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class WarnUserModal(discord.ui.Modal):
    """Modal for warning users."""
    
    def __init__(self, message: discord.Message):
        super().__init__(title="Warn User")
        self.message = message
        
        self.reason_input = discord.ui.TextInput(
            label="Warning Reason",
            placeholder="Enter the reason for this warning...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle warning submission."""
        reason = self.reason_input.value.strip()
        
        # Send warning DM to user
        try:
            warning_embed = discord.Embed(
                title=f"⚠️ Warning - {interaction.guild.name}",
                description=f"You have received a warning from our moderation team.",
                color=discord.Color.orange()
            )
            warning_embed.add_field(name="Reason", value=reason, inline=False)
            warning_embed.add_field(name="Message", value=f"[Jump to message]({self.message.jump_url})", inline=False)
            warning_embed.set_footer(text="Please review our server rules to avoid future warnings.")
            
            await self.message.author.send(embed=warning_embed)
            dm_status = "✅ DM sent"
        except discord.Forbidden:
            dm_status = "❌ DM failed (user has DMs disabled)"
        
        # Create incident record
        from database import ModerationIncident
        async with get_session() as session:
            incident = ModerationIncident(
                guild_id=interaction.guild_id,
                user_id=self.message.author.id,
                channel_id=self.message.channel.id,
                message_id=self.message.id,
                type="manual_warn",
                reason=reason,
                message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                action_taken="warn",
                moderator_id=interaction.user.id
            )
            session.add(incident)
            await session.commit()
        
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"Warning sent to {self.message.author.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="DM Status", value=dm_status, inline=True)
        
        # Log action
        bot = interaction.client
        await bot.log_action(
            interaction.guild_id,
            "User Warning",
            interaction.user,
            self.message.author,
            f"Reason: {reason}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TimeoutUserView(discord.ui.View):
    """View for timing out users."""
    
    def __init__(self, message: discord.Message):
        super().__init__(timeout=300)
        self.message = message
    
    @discord.ui.select(
        placeholder="Select timeout duration...",
        options=[
            discord.SelectOption(label="5 minutes", value="5"),
            discord.SelectOption(label="10 minutes", value="10"),
            discord.SelectOption(label="30 minutes", value="30"),
            discord.SelectOption(label="1 hour", value="60"),
            discord.SelectOption(label="2 hours", value="120"),
            discord.SelectOption(label="6 hours", value="360"),
            discord.SelectOption(label="12 hours", value="720"),
            discord.SelectOption(label="24 hours", value="1440")
        ]
    )
    async def select_duration(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Select timeout duration."""
        duration_minutes = int(select.values[0])
        
        # Open reason modal
        modal = TimeoutReasonModal(self.message, duration_minutes)
        await interaction.response.send_modal(modal)


class TimeoutReasonModal(discord.ui.Modal):
    """Modal for timeout reason."""
    
    def __init__(self, message: discord.Message, duration_minutes: int):
        super().__init__(title="Timeout User")
        self.message = message
        self.duration_minutes = duration_minutes
        
        self.reason_input = discord.ui.TextInput(
            label="Timeout Reason",
            placeholder="Enter the reason for this timeout...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle timeout submission."""
        reason = self.reason_input.value.strip()
        
        # Apply timeout
        from datetime import timedelta
        timeout_until = discord.utils.utcnow() + timedelta(minutes=self.duration_minutes)
        
        try:
            await self.message.author.timeout(timeout_until, reason=f"{reason} (by {interaction.user})")
            
            # Format duration
            if self.duration_minutes < 60:
                duration_text = f"{self.duration_minutes} minute(s)"
            else:
                hours = self.duration_minutes // 60
                minutes = self.duration_minutes % 60
                duration_text = f"{hours} hour(s)"
                if minutes > 0:
                    duration_text += f" and {minutes} minute(s)"
            
            embed = discord.Embed(
                title="⏰ User Timed Out",
                description=f"{self.message.author.mention} has been timed out for {duration_text}.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Until", value=discord.utils.format_dt(timeout_until, 'F'), inline=True)
            
            # Create incident record
            from database import ModerationIncident
            async with get_session() as session:
                incident = ModerationIncident(
                    guild_id=interaction.guild_id,
                    user_id=self.message.author.id,
                    channel_id=self.message.channel.id,
                    message_id=self.message.id,
                    type="manual_timeout",
                    reason=reason,
                    message_snapshot={"content": self.message.content, "jump_url": self.message.jump_url},
                    action_taken=f"timeout_{self.duration_minutes}m",
                    moderator_id=interaction.user.id
                )
                session.add(incident)
                await session.commit()
            
            # Log action
            bot = interaction.client
            await bot.log_action(
                interaction.guild_id,
                "User Timeout",
                interaction.user,
                self.message.author,
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


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ContextMenus(bot))