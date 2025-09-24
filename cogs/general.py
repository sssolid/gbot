"""
General commands for the Guild Management Bot - FIXED VERSION
"""
import discord
from discord.ext import commands
from typing import Optional

from database import GuildConfig, get_session
from utils.permissions import PermissionChecker


class General(commands.Cog):
    """General utility commands."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to check bot responsiveness."""
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="info", description="Show bot information")
    async def info(self, interaction: discord.Interaction):
        """Display bot information and statistics."""
        try:
            # Get guild configuration
            async with get_session() as session:
                result = await session.get(GuildConfig, interaction.guild_id)
                config = result

            embed = discord.Embed(
                title="ℹ️ Bot Information",
                description="Guild Management Bot - UI-First Discord Bot",
                color=discord.Color.blue()
            )

            # Bot stats
            embed.add_field(
                name="📊 Bot Statistics",
                value=(
                    f"**Guilds:** {len(self.bot.guilds)}\n"
                    f"**Users:** {sum(len(guild.members) for guild in self.bot.guilds)}\n"
                    f"**Latency:** {round(self.bot.latency * 1000)}ms"
                ),
                inline=True
            )

            # Guild config status
            config_status = "✅ Configured" if config else "⚠️ Not configured"
            embed.add_field(
                name="⚙️ Guild Status",
                value=(
                    f"**Configuration:** {config_status}\n"
                    f"**Members:** {len(interaction.guild.members)}\n"
                    f"**Channels:** {len(interaction.guild.channels)}"
                ),
                inline=True
            )

            # Features
            embed.add_field(
                name="🌟 Features",
                value=(
                    "• UI-First Design - No commands to remember\n"
                    "• Onboarding System - Custom questions & approval\n"
                    "• Character Profiles - Multiple characters per user\n"
                    "• Polls & Voting - Rich poll creation system\n"
                    "• Auto-Moderation - Spam & swear filtering\n"
                    "• Announcements - Scheduled & rich formatting\n"
                    "• Role Management - Admin-controlled assignments"
                ),
                inline=False
            )

            # Quick links
            embed.add_field(
                name="🔗 Quick Access",
                value=(
                    "• Use `/setup` to configure the bot\n"
                    "• Check Admin Dashboard for management\n"
                    "• Check Member Hub for user features\n"
                    "• Right-click messages/users for context actions"
                ),
                inline=False
            )

            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

        except (AttributeError, TypeError, ValueError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="ℹ️ Bot Information",
                description="Guild Management Bot - UI-First Discord Bot",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="⚠️ Configuration Issue",
                value="Some information could not be loaded. Use `/setup` to configure the bot.",
                inline=False
            )
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to retrieve bot information: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="help", description="Show help information")
    async def help_command(self, interaction: discord.Interaction):
        """Display comprehensive help information."""
        embed = discord.Embed(
            title="📚 Help - Guild Management Bot",
            description="A comprehensive Discord bot for gaming guild management",
            color=discord.Color.blue()
        )

        # For Administrators
        embed.add_field(
            name="👑 For Administrators",
            value=(
                "**Setup & Configuration:**\n"
                "• `/setup` - Initial bot configuration wizard\n"
                "• `/deploy_panels` - Deploy Admin Dashboard and Member Hub\n"
                "• `/config` - Access specific configuration sections\n\n"
                "**Admin Dashboard Features:**\n"
                "• Onboarding Queue - Review & approve new members\n"
                "• Announcements - Create server announcements\n"
                "• Role Management - Promote members & manage roles\n"
                "• Poll Builder - Create community polls\n"
                "• Moderation Center - Configure filters & view incidents\n"
                "• Profile Admin - Manage member character profiles\n"
                "• Configuration - Access all bot settings"
            ),
            inline=False
        )

        # For Members
        embed.add_field(
            name="👥 For Members",
            value=(
                "**Member Hub Features:**\n"
                "• Start Onboarding - Complete server onboarding process\n"
                "• My Characters - Manage character profiles\n"
                "• Create Poll - Create community polls (if permitted)\n"
                "• Report Message - Report inappropriate content\n"
                "• Server Info & Rules - View server information\n\n"
                "**Character Management:**\n"
                "• Create multiple characters with names & archetypes\n"
                "• Set one character as your \"main\"\n"
                "• Add build notes and playstyle descriptions\n"
                "• View other members' character profiles"
            ),
            inline=False
        )

        # Context Menus
        embed.add_field(
            name="🖱️ Context Menus (Right-click)",
            value=(
                "**On Messages:**\n"
                "• Moderate Message - Delete, warn, or timeout\n"
                "• Create Poll from Message - Turn message into poll\n\n"
                "**On Users:**\n"
                "• Manage User Roles - Add/remove roles (admin)\n"
                "• View Character Profile - See user's characters"
            ),
            inline=False
        )

        # Key Features
        embed.add_field(
            name="🌟 Key Features",
            value=(
                "• **UI-First Design** - Everything through buttons & menus\n"
                "• **Database-Driven** - All settings stored permanently\n"
                "• **Admin-Controlled** - No automatic role assignments\n"
                "• **Persistent Views** - Control panels survive bot restarts\n"
                "• **Permission-Aware** - Proper access control everywhere"
            ),
            inline=False
        )

        # Getting Started
        embed.add_field(
            name="🚀 Getting Started",
            value=(
                "1. **Admins:** Run `/setup` to configure basic settings\n"
                "2. **Deploy Panels:** Use `/deploy_panels` to add control panels\n"
                "3. **Configure Features:** Use Admin Dashboard to set up onboarding, moderation, etc.\n"
                "4. **Test Everything:** Use context menus and Member Hub features\n"
                "5. **Invite Members:** They can complete onboarding and create profiles"
            ),
            inline=False
        )

        embed.set_footer(text="For detailed setup instructions, check the documentation or ask an administrator.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="status", description="Check bot and guild configuration status")
    async def status(self, interaction: discord.Interaction):
        """Check the current status of bot configuration."""
        try:
            # Check guild configuration
            async with get_session() as session:
                config = await session.get(GuildConfig, interaction.guild_id)

            embed = discord.Embed(
                title="📋 Configuration Status",
                description=f"Status check for **{interaction.guild.name}**",
                color=discord.Color.blue()
            )

            # Basic configuration
            if config:
                # Check channels
                channels_configured = []
                if config.welcome_channel_id:
                    channel = interaction.guild.get_channel(config.welcome_channel_id)
                    channels_configured.append(f"Welcome: {channel.mention if channel else '❌ Missing'}")
                if config.logs_channel_id:
                    channel = interaction.guild.get_channel(config.logs_channel_id)
                    channels_configured.append(f"Logs: {channel.mention if channel else '❌ Missing'}")
                if config.admin_dashboard_channel_id:
                    channel = interaction.guild.get_channel(config.admin_dashboard_channel_id)
                    channels_configured.append(f"Admin Dashboard: {channel.mention if channel else '❌ Missing'}")
                if config.member_hub_channel_id:
                    channel = interaction.guild.get_channel(config.member_hub_channel_id)
                    channels_configured.append(f"Member Hub: {channel.mention if channel else '❌ Missing'}")

                embed.add_field(
                    name="📺 Configured Channels",
                    value="\n".join(channels_configured) if channels_configured else "No channels configured",
                    inline=False
                )

                # Default role
                default_role = None
                if config.default_member_role_id:
                    default_role = interaction.guild.get_role(config.default_member_role_id)

                embed.add_field(
                    name="👤 Default Member Role",
                    value=default_role.mention if default_role else "Not configured",
                    inline=True
                )

                embed.add_field(
                    name="🕐 Timezone Offset",
                    value=f"UTC{config.timezone_offset:+d}" if config.timezone_offset != 0 else "UTC",
                    inline=True
                )

                embed.add_field(
                    name="📅 Configured",
                    value=discord.utils.format_dt(config.created_at, 'R'),
                    inline=True
                )

                # Check panel deployment
                panels_status = []
                if config.admin_dashboard_message_id:
                    panels_status.append("✅ Admin Dashboard deployed")
                else:
                    panels_status.append("❌ Admin Dashboard not deployed")

                if config.member_hub_message_id:
                    panels_status.append("✅ Member Hub deployed")
                else:
                    panels_status.append("❌ Member Hub not deployed")

                embed.add_field(
                    name="🎛️ Control Panels",
                    value="\n".join(panels_status),
                    inline=False
                )

            else:
                embed.add_field(
                    name="❌ Not Configured",
                    value="This guild has not been configured yet. Run `/setup` to get started.",
                    inline=False
                )

            # Bot permissions check
            bot_permissions = interaction.guild.me.guild_permissions
            required_perms = [
                ("Manage Roles", bot_permissions.manage_roles),
                ("Send Messages", bot_permissions.send_messages),
                ("Embed Links", bot_permissions.embed_links),
                ("Read Message History", bot_permissions.read_message_history),
                ("Manage Messages", bot_permissions.manage_messages),
                ("Moderate Members", bot_permissions.moderate_members),
            ]

            perm_status = []
            for perm_name, has_perm in required_perms:
                status = "✅" if has_perm else "❌"
                perm_status.append(f"{status} {perm_name}")

            embed.add_field(
                name="🔒 Bot Permissions",
                value="\n".join(perm_status),
                inline=False
            )

        except (AttributeError, TypeError, ValueError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Configuration Error",
                description="Failed to load configuration status. Database may need initialization.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Suggested Action",
                value="Run `/setup` to initialize the bot configuration.",
                inline=False
            )
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Discord Error",
                description=f"Failed to check status: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="version", description="Show bot version information")
    async def version(self, interaction: discord.Interaction):
        """Display bot version and technical information."""
        import discord as discord_version
        import sys

        embed = discord.Embed(
            title="🔧 Version Information",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Bot Version",
            value="2.0.0 (Guild Management Bot)",
            inline=True
        )

        embed.add_field(
            name="Discord.py",
            value=f"v{discord_version.__version__}",
            inline=True
        )

        embed.add_field(
            name="Python",
            value=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            inline=True
        )

        embed.add_field(
            name="Key Features",
            value=(
                "• SQLAlchemy 2.x with async support\n"
                "• Persistent UI components\n"
                "• Database-driven configuration\n"
                "• Comprehensive permission system"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(General(bot))