"""
Configuration management views for the Guild Management Bot - FIXED VERSION
"""
import discord
from sqlalchemy import select, and_, update, delete
from typing import Dict, List, Any, Optional

from database import (
    GuildConfig, OnboardingQuestion, OnboardingRule, 
    get_session
)
from utils.permissions import PermissionChecker, require_admin


def get_config_view(config_type: str):
    """Factory function to get the appropriate configuration view."""
    config_views = {
        'config_guild_basics': GuildBasicsView,
        'config_onboarding_questions': OnboardingQuestionsView,
        'config_onboarding_rules': OnboardingRulesView,
        'config_poll_settings': PollSettingsView,
        'config_moderation': ModerationSettingsView,
        'config_panels': PanelManagementView
    }
    
    view_class = config_views.get(config_type, GuildBasicsView)
    return view_class()


class ConfigurationView(discord.ui.View):
    """Main configuration interface - this was missing!"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_configuration_menu(self, interaction: discord.Interaction):
        """Show the main configuration menu."""
        embed = discord.Embed(
            title="⚙️ Server Configuration",
            description="Select a configuration category to manage",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🏷️ Guild Basics",
            value="Server name, description, and basic settings",
            inline=False
        )
        
        embed.add_field(
            name="❓ Onboarding Questions",
            value="Manage questions for new member onboarding",
            inline=False
        )
        
        embed.add_field(
            name="📋 Onboarding Rules",
            value="Configure role assignment rules based on answers",
            inline=False
        )
        
        embed.add_field(
            name="📊 Poll Settings",
            value="Configure poll creation permissions and defaults",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Moderation",
            value="Auto-moderation features and settings",
            inline=False
        )
        
        embed.add_field(
            name="🎛️ Panels",
            value="Deploy and manage bot control panels",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.select(
        placeholder="Select configuration category...",
        options=[
            discord.SelectOption(
                label="Guild Basics",
                description="Server name, description, and basic settings",
                emoji="🏷️",
                value="guild_basics"
            ),
            discord.SelectOption(
                label="Onboarding Questions",
                description="Manage questions for new member onboarding",
                emoji="❓",
                value="onboarding_questions"
            ),
            discord.SelectOption(
                label="Onboarding Rules",
                description="Configure role assignment rules",
                emoji="📋",
                value="onboarding_rules"
            ),
            discord.SelectOption(
                label="Poll Settings",
                description="Configure poll creation permissions",
                emoji="📊",
                value="poll_settings"
            ),
            discord.SelectOption(
                label="Moderation",
                description="Auto-moderation features and settings",
                emoji="🛡️",
                value="moderation"
            ),
            discord.SelectOption(
                label="Panels",
                description="Deploy and manage bot control panels",
                emoji="🎛️",
                value="panels"
            )
        ]
    )
    async def config_select(self, interaction: discord.Interaction, menu: discord.ui.Select):
        """Handle configuration category selection."""
        category = menu.values[0]
        
        if category == "guild_basics":
            view = GuildBasicsView()
            await view.show_settings(interaction)
        elif category == "onboarding_questions":
            view = OnboardingQuestionsView()
            await view.show_questions(interaction)
        elif category == "onboarding_rules":
            view = OnboardingRulesView()
            await view.show_rules(interaction)
        elif category == "poll_settings":
            view = PollSettingsView()
            await view.show_settings(interaction)
        elif category == "moderation":
            view = ModerationSettingsView()
            await view.show_settings(interaction)
        elif category == "panels":
            view = PanelManagementView()
            await view.show_settings(interaction)


class GuildBasicsView(discord.ui.View):
    """Basic guild configuration settings."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.guild_config = None
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display guild basics settings."""
        # Load current config
        async with get_session() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            self.guild_config = result.scalar_one_or_none()
        
        embed = discord.Embed(
            title="🏷️ Guild Basics",
            description="Configure basic server settings",
            color=discord.Color.blue()
        )
        
        if self.guild_config:
            embed.add_field(
                name="Welcome Channel",
                value=f"<#{self.guild_config.welcome_channel_id}>" if self.guild_config.welcome_channel_id else "Not set",
                inline=True
            )
            
            embed.add_field(
                name="Admin Dashboard",
                value=f"<#{self.guild_config.admin_dashboard_channel_id}>" if self.guild_config.admin_dashboard_channel_id else "Not deployed",
                inline=True
            )
            
            embed.add_field(
                name="Member Hub",
                value=f"<#{self.guild_config.member_hub_channel_id}>" if self.guild_config.member_hub_channel_id else "Not deployed",
                inline=True
            )
        else:
            embed.add_field(
                name="Status",
                value="No configuration found. Settings will be created when changed.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Set welcome channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def set_welcome_channel(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Set the welcome channel."""
        channel = menu.values[0]
        
        async with get_session() as session:
            if not self.guild_config:
                self.guild_config = GuildConfig(guild_id=interaction.guild_id)
                session.add(self.guild_config)
            
            self.guild_config.welcome_channel_id = channel.id
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Welcome Channel Set",
            description=f"Welcome channel has been set to {channel.mention}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class OnboardingQuestionsView(discord.ui.View):
    """Manage onboarding questions."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.questions: List[OnboardingQuestion] = []
    
    async def show_questions(self, interaction: discord.Interaction):
        """Display onboarding questions."""
        await self.load_questions(interaction.guild_id)
        
        embed = discord.Embed(
            title="❓ Onboarding Questions",
            description="Manage questions for new member onboarding",
            color=discord.Color.blue()
        )
        
        if not self.questions:
            embed.add_field(
                name="No Questions",
                value="No onboarding questions configured. Click 'Add Question' to create one.",
                inline=False
            )
        else:
            for i, question in enumerate(self.questions[:10], 1):
                status = "✅ Active" if question.is_active else "❌ Inactive"
                embed.add_field(
                    name=f"Question {i} ({question.type}) - {status}",
                    value=f"{question.prompt[:100]}{'...' if len(question.prompt) > 100 else ''}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    async def load_questions(self, guild_id: int):
        """Load questions from database."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion)
                .where(OnboardingQuestion.guild_id == guild_id)
                .order_by(OnboardingQuestion.position)
            )
            self.questions = result.scalars().all()
    
    @discord.ui.button(label="Add Question", style=discord.ButtonStyle.primary, emoji="➕")
    async def add_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new onboarding question."""
        modal = QuestionCreationModal()
        await interaction.response.send_modal(modal)


class OnboardingRulesView(discord.ui.View):
    """Manage onboarding rules."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_rules(self, interaction: discord.Interaction):
        """Display onboarding rules."""
        embed = discord.Embed(
            title="📋 Onboarding Rules",
            description="Configure role assignment rules based on answers",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Coming Soon",
            value="Rule-based role assignment will be implemented in a future update.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class PollSettingsView(discord.ui.View):
    """Poll configuration settings."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display poll settings."""
        embed = discord.Embed(
            title="📊 Poll Settings",
            description="Configure poll creation permissions and defaults",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Who Can Create Polls",
            value="Currently: All members",
            inline=True
        )
        
        embed.add_field(
            name="Default Duration",
            value="24 hours",
            inline=True
        )
        
        embed.add_field(
            name="Max Options",
            value="10 options",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class ModerationSettingsView(discord.ui.View):
    """Moderation configuration settings."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display moderation settings."""
        embed = discord.Embed(
            title="🛡️ Moderation Settings",
            description="Configure auto-moderation features",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Spam Filter",
            value="🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Swear Filter",
            value="🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Watch Channels",
            value="None configured",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class PanelManagementView(discord.ui.View):
    """Panel deployment and management."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display panel management interface."""
        embed = discord.Embed(
            title="🎛️ Panel Management",
            description="Deploy and manage bot control panels",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Admin Dashboard",
            value="Administrative control panel for server management",
            inline=False
        )
        
        embed.add_field(
            name="Member Hub",
            value="Member interface for onboarding, profiles, and polls",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Deploy Admin Dashboard in channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def deploy_admin_dashboard(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy admin dashboard."""
        picked = menu.values[0]
        channel = interaction.guild.get_channel(picked.id) or await interaction.guild.fetch_channel(picked.id)
        
        from views.panels import AdminDashboard
        
        embed = discord.Embed(
            title="🎛️ Admin Dashboard",
            description="Administrative control panel for server management",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Features",
            value=(
                "• Onboarding queue management\n"
                "• Announcement system\n"
                "• Role and promotion tools\n"
                "• Poll creation and management\n"
                "• Moderation settings\n"
                "• Profile administration\n"
                "• Server configuration"
            ),
            inline=False
        )
        
        embed.set_footer(text="This panel is only visible to administrators")
        
        try:
            dashboard_view = AdminDashboard()
            message = await channel.send(embed=embed, view=dashboard_view)
            
            # Update guild config with dashboard location
            async with get_session() as session:
                result = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
                )
                guild_config = result.scalar_one_or_none()
                
                if not guild_config:
                    guild_config = GuildConfig(guild_id=interaction.guild_id)
                    session.add(guild_config)
                
                guild_config.admin_dashboard_channel_id = channel.id
                guild_config.admin_dashboard_message_id = message.id
                await session.commit()
            
            response_embed = discord.Embed(
                title="✅ Admin Dashboard Deployed",
                description=f"Admin dashboard has been deployed in {channel.mention}",
                color=discord.Color.green()
            )
            
        except discord.Forbidden:
            response_embed = discord.Embed(
                title="❌ Permission Error",
                description=f"I don't have permission to send messages in {channel.mention}",
                color=discord.Color.red()
            )
        except Exception as e:
            response_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to deploy dashboard: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Deploy Member Hub in channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def deploy_member_hub(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy member hub."""
        picked = menu.values[0]
        channel = interaction.guild.get_channel(picked.id) or await interaction.guild.fetch_channel(picked.id)
        
        from views.panels import MemberHub
        
        embed = discord.Embed(
            title="🏠 Member Hub",
            description="Your gateway to server features and community",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value=(
                "• Complete onboarding process\n"
                "• Create and manage character profiles\n"
                "• Participate in polls and discussions"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👤 Character Profiles",
            value="Create and manage your gaming characters with build notes and archetypes",
            inline=False
        )
        
        embed.add_field(
            name="📊 Community Features",
            value="Create polls, participate in events, and connect with other members",
            inline=False
        )
        
        try:
            hub_view = MemberHub()
            message = await channel.send(embed=embed, view=hub_view)
            
            # Update guild config with hub location
            async with get_session() as session:
                result = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
                )
                guild_config = result.scalar_one_or_none()
                
                if not guild_config:
                    guild_config = GuildConfig(guild_id=interaction.guild_id)
                    session.add(guild_config)
                
                guild_config.member_hub_channel_id = channel.id
                guild_config.member_hub_message_id = message.id
                await session.commit()
            
            response_embed = discord.Embed(
                title="✅ Member Hub Deployed",
                description=f"Member hub has been deployed in {channel.mention}",
                color=discord.Color.green()
            )
            
        except discord.Forbidden:
            response_embed = discord.Embed(
                title="❌ Permission Error",
                description=f"I don't have permission to send messages in {channel.mention}",
                color=discord.Color.red()
            )
        except Exception as e:
            response_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to deploy hub: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=response_embed, ephemeral=True)


# This is the PanelDeploymentView that was referenced in panels.py but didn't exist
# It's now an alias to PanelManagementView for compatibility
class PanelDeploymentView(PanelManagementView):
    """Panel deployment view - alias for PanelManagementView."""
    
    async def show_deployment_options(self, interaction: discord.Interaction):
        """Show deployment options - delegates to show_settings."""
        await self.show_settings(interaction)


class QuestionCreationModal(discord.ui.Modal):
    """Modal for creating onboarding questions."""
    
    def __init__(self):
        super().__init__(title="Create Onboarding Question")
        
        self.prompt_input = discord.ui.TextInput(
            label="Question Prompt",
            placeholder="Enter the question you want to ask new members...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        
        self.type_input = discord.ui.TextInput(
            label="Question Type",
            placeholder="text or single_select",
            required=True,
            max_length=20
        )
        
        self.options_input = discord.ui.TextInput(
            label="Options (for single_select)",
            placeholder="Option 1, Option 2, Option 3...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        
        self.add_item(self.prompt_input)
        self.add_item(self.type_input)
        self.add_item(self.options_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle question creation."""
        prompt = self.prompt_input.value.strip()
        question_type = self.type_input.value.strip().lower()
        options_text = self.options_input.value.strip()
        
        if question_type not in ['text', 'single_select']:
            await interaction.response.send_message(
                "❌ Question type must be either 'text' or 'single_select'",
                ephemeral=True
            )
            return
        
        options = []
        if question_type == 'single_select' and options_text:
            options = [opt.strip() for opt in options_text.split(',') if opt.strip()]
        
        async with get_session() as session:
            # Get next position
            result = await session.execute(
                select(OnboardingQuestion)
                .where(OnboardingQuestion.guild_id == interaction.guild_id)
                .order_by(OnboardingQuestion.position.desc())
                .limit(1)
            )
            last_question = result.scalar_one_or_none()
            position = (last_question.position + 1) if last_question else 1
            
            # Create question
            question = OnboardingQuestion(
                guild_id=interaction.guild_id,
                qid=f"q{position}",
                prompt=prompt,
                type=question_type,
                required=True,
                options=options if options else None,
                position=position,
                is_active=True
            )
            
            session.add(question)
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Question Created",
            description=f"Successfully created onboarding question at position {position}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)