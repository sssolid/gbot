"""
Enhanced configuration cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from views.configuration import get_config_view, ConfigurationView
from utils.permissions import PermissionChecker
from database import get_guild_config, GuildConfig


class ConfigurationCog(commands.Cog):
    """Enhanced configuration management with proper timezone handling."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Initial server setup wizard (Admin only)")
    async def setup_command(self, interaction: discord.Interaction):
        """Run the initial setup wizard."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "run setup",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = SetupWizardView()

        embed = discord.Embed(
            title="🛠️ Guild Management Bot Setup",
            description="Welcome! Let's get your server configured with the Guild Management Bot.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Setup Steps",
            value="1. **Basic Configuration** - Set essential channels and roles\n"
                  "2. **Deploy Panels** - Add control panels to your server\n"
                  "3. **Onboarding Setup** - Configure member onboarding\n"
                  "4. **Moderation Setup** - Set up auto-moderation",
            inline=False
        )

        embed.add_field(
            name="Getting Started",
            value="Click the buttons below to configure different aspects of the bot.",
            inline=False
        )

        embed.set_footer(text="💡 You can access these settings anytime with /config")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="deploy_panels", description="Deploy bot control panels (Admin only)")
    async def deploy_panels_command(self, interaction: discord.Interaction):
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

        if hasattr(view, 'show_settings'):
            await view.show_settings(interaction)
        elif hasattr(view, 'show_questions'):
            await view.show_questions(interaction)
        elif hasattr(view, 'show_rules'):
            await view.show_rules(interaction)
        else:
            # Fallback to general config menu
            config_view = ConfigurationView()
            await config_view.show_configuration_menu(interaction)

    @app_commands.command(name="info", description="Show bot information and status")
    async def info_command(self, interaction: discord.Interaction):
        """Show bot information and current configuration."""
        guild_config = await get_guild_config(interaction.guild_id)

        embed = discord.Embed(
            title="🤖 Guild Management Bot",
            description="Comprehensive guild management with UI-first design",
            color=discord.Color.blue()
        )

        # Bot status
        embed.add_field(
            name="📊 Bot Status",
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n"
                  f"**Guilds:** {len(self.bot.guilds)}\n"
                  f"**Version:** 2.0.0",
            inline=True
        )

        # Guild configuration status
        config_status = []
        if guild_config:
            if guild_config.welcome_channel_id:
                config_status.append("✅ Welcome Channel")
            if guild_config.logs_channel_id:
                config_status.append("✅ Logs Channel")
            if guild_config.announcements_channel_id:
                config_status.append("✅ Announcements Channel")
            if guild_config.default_member_role_id:
                config_status.append("✅ Default Member Role")
            if guild_config.admin_dashboard_channel_id:
                config_status.append("✅ Admin Dashboard")
            if guild_config.member_hub_channel_id:
                config_status.append("✅ Member Hub")

        if not config_status:
            config_status.append("⚠️ No configuration found")

        embed.add_field(
            name="⚙️ Configuration",
            value="\n".join(config_status[:10]),  # Limit to 10 items
            inline=True
        )

        # Features
        embed.add_field(
            name="🌟 Key Features",
            value="• Enhanced Onboarding with MO2 support\n"
                  "• Character Profile Management\n"
                  "• Message Logging & Audit\n"
                  "• Poll System\n"
                  "• Admin Dashboard\n"
                  "• Member Hub",
            inline=False
        )

        # Timezone info
        if guild_config and guild_config.timezone_offset is not None:
            offset = guild_config.timezone_offset
            offset_str = f"UTC{'+' if offset >= 0 else ''}{offset}:00"
            embed.add_field(
                name="🌍 Server Timezone",
                value=offset_str,
                inline=True
            )

        embed.set_footer(text=f"Bot ID: {self.bot.user.id}")

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetupWizardView(discord.ui.View):
    """Enhanced setup wizard view for initial configuration."""

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
        embed = discord.Embed(
            title="🛡️ Moderation Setup",
            description="Enhanced moderation features are configured automatically.\n\n**Features enabled:**\n• Message logging for audit purposes\n• Context menu moderation tools\n• Incident tracking",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Auto-Moderation",
            value="Advanced filtering can be configured through the admin dashboard once deployed.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Help & Documentation", style=discord.ButtonStyle.secondary, emoji="📚")
    async def help_docs(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show help and documentation."""
        embed = discord.Embed(
            title="📚 Help & Documentation",
            description="Guild Management Bot - Quick Reference",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎛️ Admin Commands",
            value="• `/setup` - Initial configuration wizard\n"
                  "• `/config` - Access configuration sections\n"
                  "• `/deploy_panels` - Deploy control panels\n"
                  "• `/character_stats` - View guild character stats",
            inline=False
        )

        embed.add_field(
            name="👤 Member Commands",
            value="• `/characters` - Manage character profiles\n"
                  "• `/main_character` - View your main character\n"
                  "• `/view_profile @user` - View someone's profile",
            inline=False
        )

        embed.add_field(
            name="🎯 Key Features",
            value="• **Enhanced Onboarding**: MO2-specific questions with timezone support\n"
                  "• **Character Profiles**: Detailed MO2 character management\n"
                  "• **Message Logging**: Complete audit trail\n"
                  "• **Admin Dashboard**: Centralized control panel",
            inline=False
        )

        embed.add_field(
            name="🆘 Support",
            value="Use the control panels for most tasks. Right-click messages/users for quick actions.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ConfigurationCog(bot))