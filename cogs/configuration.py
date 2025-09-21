"""
Configuration cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands

from views.configuration import get_config_view
from utils.permissions import PermissionChecker


class ConfigurationCog(commands.Cog):
    """Handles configuration commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="deploy_panels", description="Deploy bot control panels (Admin only)")
    async def deploy_panels(self, interaction: discord.Interaction):
        """Deploy the main bot panels."""
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
    
    @app_commands.command(name="config", description="Open configuration menu (Admin only)")
    @app_commands.describe(
        section="Configuration section to open"
    )
    @app_commands.choices(section=[
        app_commands.Choice(name="Guild Basics", value="config_guild_basics"),
        app_commands.Choice(name="Onboarding Questions", value="config_onboarding_questions"),
        app_commands.Choice(name="Onboarding Rules", value="config_onboarding_rules"),
        app_commands.Choice(name="Poll Settings", value="config_poll_settings"),
        app_commands.Choice(name="Moderation", value="config_moderation"),
        app_commands.Choice(name="Panels", value="config_panels")
    ])
    async def config_command(self, interaction: discord.Interaction, section: str = "config_guild_basics"):
        """Open configuration interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access configuration",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = get_config_view(section)
        
        section_names = {
            "config_guild_basics": "Guild Basics",
            "config_onboarding_questions": "Onboarding Questions", 
            "config_onboarding_rules": "Onboarding Rules",
            "config_poll_settings": "Poll Settings",
            "config_moderation": "Moderation Settings",
            "config_panels": "Panel Management"
        }
        
        section_name = section_names.get(section, "Configuration")
        
        # Different sections have different show methods
        if section == "config_guild_basics":
            await view.show_settings(interaction)
        elif section == "config_onboarding_questions":
            await view.show_questions(interaction)
        elif section == "config_onboarding_rules":
            await view.show_rules(interaction)
        elif section == "config_panels":
            await view.show_settings(interaction)
        else:
            await view.show_settings(interaction)
    
    @app_commands.command(name="setup", description="Initial bot setup wizard (Admin only)")
    async def setup_wizard(self, interaction: discord.Interaction):
        """Run initial setup wizard."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "run setup wizard",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛠️ Bot Setup Wizard",
            description="Welcome to the Guild Management Bot! Let's get you set up.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔧 Step 1: Basic Configuration",
            value="Set up channels, roles, and basic settings",
            inline=False
        )
        
        embed.add_field(
            name="📋 Step 2: Deploy Panels",
            value="Deploy the Admin Dashboard and Member Hub",
            inline=False
        )
        
        embed.add_field(
            name="❓ Step 3: Configure Onboarding",
            value="Set up questions and rules for new members",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Step 4: Moderation Settings",
            value="Configure spam filters and moderation tools",
            inline=False
        )
        
        view = SetupWizardView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="info", description="Show bot information and status")
    async def info(self, interaction: discord.Interaction):
        """Show bot information."""
        embed = discord.Embed(
            title="🤖 Guild Management Bot",
            description="A comprehensive Discord bot for gaming guild management",
            color=discord.Color.blue()
        )
        
        # Bot stats
        embed.add_field(
            name="📊 Statistics",
            value=(
                f"**Guilds:** {len(self.bot.guilds)}\n"
                f"**Users:** {len(self.bot.users)}\n"
                f"**Commands:** {len(self.bot.tree.get_commands())}"
            ),
            inline=True
        )
        
        # Features
        embed.add_field(
            name="🔹 Features",
            value=(
                "• UI-first design (no command memorization)\n"
                "• Onboarding with role suggestions\n"
                "• Character profile management\n"
                "• Poll system with anonymous voting\n"
                "• Auto-moderation (spam/swear filters)\n"
                "• Announcement system\n"
                "• Admin approval workflows"
            ),
            inline=True
        )
        
        # Configuration status for this guild
        guild_config = await self.bot.get_guild_config(interaction.guild_id)
        
        config_status = []
        if guild_config:
            if guild_config.welcome_channel_id:
                config_status.append("✅ Welcome channel set")
            else:
                config_status.append("❌ Welcome channel not set")
            
            if guild_config.logs_channel_id:
                config_status.append("✅ Logs channel set")
            else:
                config_status.append("❌ Logs channel not set")
            
            if guild_config.admin_dashboard_message_id:
                config_status.append("✅ Admin dashboard deployed")
            else:
                config_status.append("❌ Admin dashboard not deployed")
            
            if guild_config.member_hub_message_id:
                config_status.append("✅ Member hub deployed")
            else:
                config_status.append("❌ Member hub not deployed")
        else:
            config_status = ["❌ No configuration found"]
        
        embed.add_field(
            name="⚙️ Guild Configuration",
            value="\n".join(config_status),
            inline=False
        )
        
        if PermissionChecker.is_admin(interaction.user):
            embed.add_field(
                name="🔧 Admin Actions",
                value="Use `/setup` to configure the bot or `/config` to access specific settings.",
                inline=False
            )
        
        embed.set_footer(text=f"Bot latency: {round(self.bot.latency * 1000)}ms")
        
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetupWizardView(discord.ui.View):
    """Setup wizard view for initial configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Basic Configuration", style=discord.ButtonStyle.primary, emoji="🔧")
    async def basic_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open basic configuration."""
        from views.configuration import GuildBasicsView
        view = GuildBasicsView()
        await view.show_settings(interaction)
    
    @discord.ui.button(label="Deploy Panels", style=discord.ButtonStyle.primary, emoji="📋")
    async def deploy_panels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deploy control panels."""
        from views.configuration import PanelManagementView
        view = PanelManagementView()
        await view.show_settings(interaction)
    
    @discord.ui.button(label="Onboarding Setup", style=discord.ButtonStyle.secondary, emoji="❓")
    async def onboarding_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set up onboarding."""
        from views.configuration import OnboardingQuestionsView
        view = OnboardingQuestionsView()
        await view.show_questions(interaction)
    
    @discord.ui.button(label="Moderation Setup", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def moderation_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set up moderation."""
        from views.moderation import ModerationCenterView
        view = ModerationCenterView()
        
        embed = discord.Embed(
            title="🛡️ Moderation Setup",
            description="Configure auto-moderation features for your server.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Help & Documentation", style=discord.ButtonStyle.secondary, emoji="📚")
    async def help_docs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show help and documentation."""
        embed = discord.Embed(
            title="📚 Help & Documentation",
            description="Everything you need to know about the Guild Management Bot",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎛️ Control Panels",
            value=(
                "The bot operates through two main panels:\n"
                "• **Admin Dashboard** - For administrators to manage the server\n"
                "• **Member Hub** - For members to access features\n\n"
                "Deploy these panels using the 'Deploy Panels' button above."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📝 Onboarding System",
            value=(
                "• Create custom questions for new members\n"
                "• Set up rules to automatically suggest roles\n"
                "• Administrators approve/deny applications\n"
                "• No automatic role assignment - admin approval required"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👤 Character Profiles",
            value=(
                "• Members can create multiple gaming characters\n"
                "• Set one character as 'main'\n"
                "• Include archetype/class and build notes\n"
                "• Admins can view and manage all profiles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Polls & Announcements",
            value=(
                "• Create polls with up to 10 options\n"
                "• Support for anonymous voting\n"
                "• Rich announcement system with scheduling\n"
                "• All actions logged for transparency"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "• Spam filter with configurable thresholds\n"
                "• Swear filter with custom word lists\n"
                "• Staff role exemptions\n"
                "• Channel-specific moderation\n"
                "• Incident logging and reporting"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Getting Started",
            value=(
                "1. Run `/setup` to begin configuration\n"
                "2. Set basic settings (channels, roles)\n"
                "3. Deploy the Admin Dashboard and Member Hub\n"
                "4. Configure onboarding questions\n"
                "5. Set up moderation if desired\n"
                "6. Test features with your team"
            ),
            inline=False
        )
        
        embed.set_footer(text="For more help, contact your bot administrator")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ConfigurationCog(bot))