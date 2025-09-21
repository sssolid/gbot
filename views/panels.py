"""
Main persistent panel views for the Guild Management Bot
"""
import discord
from discord.ext import commands
from typing import Optional

from utils.permissions import PermissionChecker, require_admin


class AdminDashboard(discord.ui.View):
    """Persistent Admin Dashboard panel."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Onboarding Queue",
        style=discord.ButtonStyle.primary,
        emoji="📋",
        custom_id="admin_dashboard:onboarding_queue"
    )
    async def onboarding_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the onboarding queue."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access the onboarding queue",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.onboarding import OnboardingQueueView
        await interaction.response.send_message(
            "Loading onboarding queue...",
            view=OnboardingQueueView(),
            ephemeral=True
        )
    
    @discord.ui.button(
        label="Announcements",
        style=discord.ButtonStyle.secondary,
        emoji="📢",
        custom_id="admin_dashboard:announcements"
    )
    async def announcements(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open announcement composer."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.announcements import AnnouncementModal
        await interaction.response.send_modal(AnnouncementModal())
    
    @discord.ui.button(
        label="Promotions & Roles",
        style=discord.ButtonStyle.secondary,
        emoji="🎭",
        custom_id="admin_dashboard:role_manager"
    )
    async def role_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open role management interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.moderation import RoleManagerView
        await interaction.response.send_message(
            "Role Management",
            view=RoleManagerView(),
            ephemeral=True
        )
    
    @discord.ui.button(
        label="Poll Builder",
        style=discord.ButtonStyle.secondary,
        emoji="📊",
        custom_id="admin_dashboard:poll_builder"
    )
    async def poll_builder(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open poll builder."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.polls import PollBuilderModal
        await interaction.response.send_modal(PollBuilderModal())
    
    @discord.ui.button(
        label="Moderation Center",
        style=discord.ButtonStyle.danger,
        emoji="🛡️",
        custom_id="admin_dashboard:moderation"
    )
    async def moderation_center(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open moderation settings."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access moderation settings",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.moderation import ModerationCenterView
        await interaction.response.send_message(
            "Moderation Center",
            view=ModerationCenterView(),
            ephemeral=True
        )
    
    @discord.ui.button(
        label="Profiles Admin",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="admin_dashboard:profiles_admin"
    )
    async def profiles_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open profile administration."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage profiles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.profiles import ProfileAdminView
        await interaction.response.send_message(
            "Profile Administration",
            view=ProfileAdminView(),
            ephemeral=True
        )
    
    @discord.ui.select(
        placeholder="Configuration Settings",
        options=[
            discord.SelectOption(
                label="Guild Basics",
                value="config_guild_basics",
                description="Basic guild settings",
                emoji="⚙️"
            ),
            discord.SelectOption(
                label="Onboarding Questions",
                value="config_onboarding_questions",
                description="Manage onboarding questions",
                emoji="❓"
            ),
            discord.SelectOption(
                label="Onboarding Rules",
                value="config_onboarding_rules", 
                description="Role suggestion rules",
                emoji="📏"
            ),
            discord.SelectOption(
                label="Poll Settings",
                value="config_poll_settings",
                description="Default poll configuration",
                emoji="📊"
            ),
            discord.SelectOption(
                label="Moderation Settings",
                value="config_moderation",
                description="Spam and swear filters",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="Panel Management",
                value="config_panels",
                description="Deploy and manage panels",
                emoji="🎛️"
            )
        ],
        custom_id="admin_dashboard:configuration"
    )
    async def configuration(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Open configuration sections."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access configuration",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.configuration import get_config_view
        config_type = select.values[0]
        view = get_config_view(config_type)
        
        await interaction.response.send_message(
            f"Configuration: {select.values[0].replace('config_', '').replace('_', ' ').title()}",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(
        label="Help & Shortcuts",
        style=discord.ButtonStyle.secondary,
        emoji="❓",
        custom_id="admin_dashboard:help",
        row=2
    )
    async def help_shortcuts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show help information."""
        embed = discord.Embed(
            title="📋 Admin Dashboard Help",
            description="This dashboard provides access to all administrative functions.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔹 Main Functions",
            value=(
                "• **Onboarding Queue**: Review and approve new member applications\n"
                "• **Announcements**: Create and schedule server announcements\n"
                "• **Promotions & Roles**: Manage member roles and promotions\n"
                "• **Poll Builder**: Create polls for the community\n"
                "• **Moderation Center**: Configure auto-moderation settings\n"
                "• **Profiles Admin**: Manage member character profiles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔹 Configuration",
            value=(
                "Use the dropdown to access:\n"
                "• Guild settings and channels\n"
                "• Onboarding questions and rules\n"
                "• Poll and moderation settings\n"
                "• Panel deployment tools"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔹 Context Menus",
            value=(
                "Right-click messages/users for quick actions:\n"
                "• Moderate messages\n"
                "• Manage user roles\n"
                "• View user profiles"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MemberHub(discord.ui.View):
    """Persistent Member Hub panel."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Start Onboarding",
        style=discord.ButtonStyle.primary,
        emoji="🚀",
        custom_id="member_hub:start_onboarding"
    )
    async def start_onboarding(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the onboarding process."""
        from views.onboarding import OnboardingWizard
        await interaction.response.send_message(
            "Starting onboarding process...",
            view=OnboardingWizard(),
            ephemeral=True
        )
    
    @discord.ui.button(
        label="My Characters",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="member_hub:my_characters"
    )
    async def my_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage character profiles."""
        from views.profiles import CharacterManagerView
        await interaction.response.send_message(
            "Character Manager",
            view=CharacterManagerView(interaction.user.id),
            ephemeral=True
        )
    
    @discord.ui.button(
        label="Create Poll",
        style=discord.ButtonStyle.secondary,
        emoji="📊",
        custom_id="member_hub:create_poll"
    )
    async def create_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a poll (if permitted)."""
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
        
        from views.polls import PollBuilderModal
        await interaction.response.send_modal(PollBuilderModal())
    
    @discord.ui.button(
        label="Report Message",
        style=discord.ButtonStyle.danger,
        emoji="🚨",
        custom_id="member_hub:report_message"
    )
    async def report_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Report abuse or inappropriate content."""
        from views.moderation import ReportModal
        await interaction.response.send_modal(ReportModal())
    
    @discord.ui.button(
        label="Server Info & Rules",
        style=discord.ButtonStyle.secondary,
        emoji="📜",
        custom_id="member_hub:server_info"
    )
    async def server_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show server information and rules."""
        embed = discord.Embed(
            title=f"📜 {interaction.guild.name} - Server Information",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔹 About This Server",
            value=(
                f"Welcome to **{interaction.guild.name}**!\n\n"
                f"**Members**: {interaction.guild.member_count:,}\n"
                f"**Created**: {discord.utils.format_dt(interaction.guild.created_at, 'D')}\n"
                f"**Owner**: {interaction.guild.owner.mention if interaction.guild.owner else 'Unknown'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔹 Getting Started",
            value=(
                "1. Complete the **onboarding process** to get your roles\n"
                "2. Set up your **character profile** to introduce yourself\n"
                "3. Read the server rules and guidelines\n"
                "4. Join the community discussions!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔹 Need Help?",
            value=(
                "• Use the **Report Message** button for inappropriate content\n"
                "• Contact server moderators for assistance\n"
                "• Check pinned messages in channels for guidelines"
            ),
            inline=False
        )
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)