"""
Main persistent panel views for the Guild Management Bot - MINIMAL FIX
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
        
        # Create and load the queue view
        queue_view = OnboardingQueueView()
        
        # Show loading message first
        embed = discord.Embed(
            title="📋 Loading Onboarding Queue...",
            description="Please wait while we fetch the pending applications.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Load and show the actual queue
        await queue_view.show_queue(interaction)
    
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
        
        from views.roles import RoleManagerView
        view = RoleManagerView()
        await view.show_role_interface(interaction)
    
    @discord.ui.button(
        label="Polls Manager",
        style=discord.ButtonStyle.secondary,
        emoji="📊",
        custom_id="admin_dashboard:poll_manager"
    )
    async def poll_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open poll management interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.polls import PollManagerView
        view = PollManagerView()
        await view.show_poll_manager(interaction)
    
    @discord.ui.button(
        label="Moderation Center",
        style=discord.ButtonStyle.secondary,
        emoji="🛡️",
        custom_id="admin_dashboard:moderation_center",
        row=1
    )
    async def moderation_center(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open moderation center."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access moderation center",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.moderation import ModerationCenterView
        view = ModerationCenterView()
        
        embed = discord.Embed(
            title="🛡️ Moderation Center",
            description="Configure and monitor server moderation features",
            color=discord.Color.red()
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
    
    @discord.ui.button(
        label="Profiles Admin",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="admin_dashboard:profiles_admin"
    )
    async def profiles_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open profiles administration."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage member profiles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.profiles import ProfileAdminView
        view = ProfileAdminView()
        await view.show_admin_interface(interaction)
    
    @discord.ui.button(
        label="Configuration",
        style=discord.ButtonStyle.secondary,
        emoji="⚙️",
        custom_id="admin_dashboard:configuration",
        row=2
    )
    async def configuration(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open configuration interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access configuration",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.configuration import ConfigurationView
        view = ConfigurationView()
        await view.show_configuration_menu(interaction)
    
    @discord.ui.button(
        label="Deploy Panels",
        style=discord.ButtonStyle.secondary,
        emoji="🚀",
        custom_id="admin_dashboard:deploy_panels",
        row=2
    )
    async def deploy_panels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deploy control panels."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "deploy panels",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.configuration import PanelManagementView
        view = PanelManagementView()
        await view.show_settings(interaction)


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
        # Check if user has an existing session
        from database import get_session, OnboardingSession
        from sqlalchemy import select, and_
        
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.user_id == interaction.user.id,
                        OnboardingSession.guild_id == interaction.guild_id,
                        OnboardingSession.state == 'in_progress'
                    )
                )
            )
            existing_session = result.scalar_one_or_none()
        
        if existing_session:
            embed = discord.Embed(
                title="📝 Continue Onboarding",
                description="You have an onboarding session in progress. Would you like to continue?",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="🚀 Start Onboarding",
                description="Welcome! Let's get you set up in this server.",
                color=discord.Color.green()
            )
        
        from views.onboarding import OnboardingWizard
        wizard = OnboardingWizard(existing_session.id if existing_session else None)
        await wizard.load_questions(interaction.guild_id)
        await wizard.load_session(interaction.user.id, interaction.guild_id)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await wizard.show_current_question(interaction)
    
    @discord.ui.button(
        label="My Characters",
        style=discord.ButtonStyle.secondary,
        emoji="👤",
        custom_id="member_hub:my_characters"
    )
    async def my_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage character profiles."""
        from views.profiles import CharacterManagerView
        view = CharacterManagerView(interaction.user.id)
        await view.show_characters(interaction)
    
    @discord.ui.button(
        label="Create Poll",
        style=discord.ButtonStyle.secondary,
        emoji="📊",
        custom_id="member_hub:create_poll"
    )
    async def create_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a poll (if user has permission)."""
        # Check if user has poll creation permission
        can_create_polls = (
            PermissionChecker.is_admin(interaction.user) or
            any(role.name.lower() in ['member', 'verified'] for role in interaction.user.roles)
        )
        
        if not can_create_polls:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You don't have permission to create polls. Please complete onboarding first.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.polls import PollBuilderModal
        modal = PollBuilderModal()
        await interaction.response.send_modal(modal)