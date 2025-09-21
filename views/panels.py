"""
Main persistent panel views for the Guild Management Bot - FIXED VERSION
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
        
        from views.profiles import RoleManagementView
        view = RoleManagementView()
        await view.show_role_management(interaction)
    
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
        
        from views.polls import PollCreationModal
        await interaction.response.send_modal(PollCreationModal())
    
    @discord.ui.button(
        label="Moderation Center",
        style=discord.ButtonStyle.danger,
        emoji="🛡️",
        custom_id="admin_dashboard:moderation"
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
            description="Configure and manage server moderation settings.",
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
        
        from views.configuration import PanelDeploymentView
        view = PanelDeploymentView()
        await view.show_deployment_options(interaction)


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
        from database import get_user_onboarding_session
        
        existing_session = await get_user_onboarding_session(
            interaction.guild_id, 
            interaction.user.id, 
            'in_progress'
        )
        
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
        # Check if user can create polls
        if hasattr(interaction.client, 'config_cache'):
            poll_config = await interaction.client.config_cache.get_poll_config(interaction.guild_id)
            creator_roles = poll_config.get('creator_roles', [])
            
            user_can_create = (
                PermissionChecker.is_admin(interaction.user) or
                any(str(role.id) in creator_roles for role in interaction.user.roles)
            )
            
            if not user_can_create and creator_roles:
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="You don't have permission to create polls.",
                    color=discord.Color.red()
                )
                
                if creator_roles:
                    role_mentions = []
                    for role_id in creator_roles:
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            role_mentions.append(role.mention)
                    
                    if role_mentions:
                        embed.add_field(
                            name="Required Roles",
                            value="\n".join(role_mentions),
                            inline=False
                        )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        from views.polls import PollCreationModal
        await interaction.response.send_modal(PollCreationModal())
    
    @discord.ui.button(
        label="Report Message",
        style=discord.ButtonStyle.danger,
        emoji="⚠️",
        custom_id="member_hub:report_message"
    )
    async def report_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Report a message to moderators."""
        from views.moderation import ReportMessageModal
        modal = ReportMessageModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Server Info & Rules",
        style=discord.ButtonStyle.secondary,
        emoji="ℹ️",
        custom_id="member_hub:server_info"
    )
    async def server_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display server information and rules."""
        embed = discord.Embed(
            title=f"ℹ️ {interaction.guild.name} - Server Information",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Server Stats",
            value=(
                f"**Members:** {interaction.guild.member_count:,}\n"
                f"**Created:** {discord.utils.format_dt(interaction.guild.created_at, 'D')}\n"
                f"**Owner:** {interaction.guild.owner.mention if interaction.guild.owner else 'Unknown'}"
            ),
            inline=True
        )
        
        embed.add_field(
            name="📋 Features",
            value=(
                "• Character profile management\n"
                "• Community polls and voting\n"
                "• Automated moderation\n"
                "• Member onboarding system\n"
                "• Server announcements"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🤝 Getting Help",
            value=(
                "• Use `/help` for bot commands\n"
                "• Contact server administrators\n"
                "• Check pinned messages in channels\n"
                "• Use the report feature for issues"
            ),
            inline=False
        )
        
        if interaction.guild.description:
            embed.add_field(
                name="📝 Server Description",
                value=interaction.guild.description,
                inline=False
            )
        
        if interaction.guild.rules_channel:
            embed.add_field(
                name="📜 Server Rules",
                value=f"Please review the rules in {interaction.guild.rules_channel.mention}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ReportMessageModal(discord.ui.Modal):
    """Modal for reporting messages."""
    
    def __init__(self):
        super().__init__(title="Report Message")
        
        self.message_link = discord.ui.TextInput(
            label="Message Link",
            placeholder="Right-click message → Copy Message Link",
            required=True,
            max_length=500
        )
        self.add_item(self.message_link)
        
        self.reason = discord.ui.TextInput(
            label="Reason for Report",
            placeholder="Describe why you're reporting this message...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle report submission."""
        # Extract message info from link
        message_link = self.message_link.value
        reason = self.reason.value
        
        # Validate message link format
        if not message_link.startswith('https://discord.com/channels/'):
            embed = discord.Embed(
                title="❌ Invalid Message Link",
                description="Please provide a valid Discord message link.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Send report to logs channel
        if hasattr(interaction.client, 'config_cache'):
            guild_config = await interaction.client.config_cache.get_guild_config(interaction.guild_id)
            if guild_config and guild_config.logs_channel_id:
                logs_channel = interaction.guild.get_channel(guild_config.logs_channel_id)
                if logs_channel:
                    report_embed = discord.Embed(
                        title="🚨 Message Report",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    report_embed.add_field(
                        name="Reporter",
                        value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                        inline=True
                    )
                    
                    report_embed.add_field(
                        name="Message Link",
                        value=f"[Jump to Message]({message_link})",
                        inline=True
                    )
                    
                    report_embed.add_field(
                        name="Reason",
                        value=reason,
                        inline=False
                    )
                    
                    try:
                        await logs_channel.send(embed=report_embed)
                    except discord.Forbidden:
                        pass  # No permission to send to logs channel
        
        # Confirm to user
        embed = discord.Embed(
            title="✅ Report Submitted",
            description="Your report has been submitted to the moderation team. Thank you for helping keep the server safe!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)