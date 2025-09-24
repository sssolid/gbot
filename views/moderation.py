"""
Moderation features for the Guild Management Bot - FIXED VERSION
"""
from typing import List
from datetime import datetime, timezone

import discord
from sqlalchemy import select, and_, update
from discord.ext import commands

from database import ModerationIncident, ModerationLog, OnboardingSession, get_session
from utils.permissions import PermissionChecker


class ModerationCenterView(discord.ui.View):
    """Main moderation center interface."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="Spam Filter Settings",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🚫",
        row=0
    )
    async def spam_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open spam filter settings."""
        view = SpamFilterView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)

    @discord.ui.button(
        label="Swear Filter Settings",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🤬",
        row=0
    )
    async def swear_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open swear filter settings."""
        view = SwearFilterView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)

    @discord.ui.button(
        label="Watch Channels",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="👁️",
        row=1
    )
    async def watch_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure watched channels."""
        view = WatchChannelsView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)

    @discord.ui.button(
        label="Staff Exemptions",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🛡️",
        row=1
    )
    async def staff_exemptions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure staff role exemptions."""
        view = StaffExemptionsView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)

    @discord.ui.button(
        label="Recent Incidents",
        style=discord.ButtonStyle.primary, # type: ignore[arg-type]
        emoji="📋",
        row=2
    )
    async def recent_incidents(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View recent moderation incidents."""
        view = IncidentLogView()
        await view.show_incidents(interaction)

    @discord.ui.button(
        label="Admin Testing",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🧪",
        row=2
    )
    async def admin_testing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Admin testing tools."""
        view = AdminTestingView()
        await view.show_testing_options(interaction)


class SpamFilterView(discord.ui.View):
    """Spam filter configuration."""

    def __init__(self):
        super().__init__(timeout=300)
        self.max_messages = 5
        self.time_window = 10  # seconds
        self.max_mentions = 5
        self.action = "delete"  # delete, warn, timeout
        self.timeout_duration = 300  # 5 minutes

    async def load_settings(self, guild_id: int, bot):
        """Load spam filter settings."""
        try:
            from utils.cache import get_config
            config = await get_config(bot, guild_id, "spam_filter", {})

            self.max_messages = config.get("max_messages", 5)
            self.time_window = config.get("time_window", 10)
            self.max_mentions = config.get("max_mentions", 5)
            self.action = config.get("action", "delete")
            self.timeout_duration = config.get("timeout_duration", 300)
        except (AttributeError, TypeError, ValueError) as e:
            # Use defaults if loading fails
            pass

    async def save_settings(self, guild_id: int, bot):
        """Save spam filter settings."""
        try:
            from utils.cache import set_config
            config = {
                "max_messages": self.max_messages,
                "time_window": self.time_window,
                "max_mentions": self.max_mentions,
                "action": self.action,
                "timeout_duration": self.timeout_duration
            }
            await set_config(bot, guild_id, "spam_filter", config)
        except (AttributeError, TypeError, ValueError) as e:
            raise commands.CommandError(f"Failed to save spam filter settings: {str(e)}")

    async def show_settings(self, interaction: discord.Interaction):
        """Display current spam filter settings."""
        embed = discord.Embed(
            title="🚫 Spam Filter Settings",
            description="Configure automatic spam detection and response",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Message Limits",
            value=f"**Max Messages:** {self.max_messages} messages\n**Time Window:** {self.time_window} seconds",
            inline=True
        )

        embed.add_field(
            name="Mention Limits",
            value=f"**Max Mentions:** {self.max_mentions} per message",
            inline=True
        )

        embed.add_field(
            name="Actions",
            value=f"**Action:** {self.action.title()}\n" +
                  (f"**Timeout Duration:** {self.timeout_duration//60} minutes" if self.action == "timeout" else ""),
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class SwearFilterView(discord.ui.View):
    """Swear filter configuration."""

    def __init__(self):
        super().__init__(timeout=300)
        self.words = []
        self.action = "delete"
        self.timeout_duration = 300

    async def load_settings(self, guild_id: int, bot):
        """Load swear filter settings."""
        try:
            from utils.cache import get_config
            config = await get_config(bot, guild_id, "swear_filter", {})

            self.words = config.get("words", [])
            self.action = config.get("action", "delete")
            self.timeout_duration = config.get("timeout_duration", 300)
        except (AttributeError, TypeError, ValueError) as e:
            # Use defaults if loading fails
            pass

    async def save_settings(self, guild_id: int, bot):
        """Save swear filter settings."""
        try:
            from utils.cache import set_config
            config = {
                "words": self.words,
                "action": self.action,
                "timeout_duration": self.timeout_duration
            }
            await set_config(bot, guild_id, "swear_filter", config)
        except (AttributeError, TypeError, ValueError) as e:
            raise commands.CommandError(f"Failed to save swear filter settings: {str(e)}")

    async def show_settings(self, interaction: discord.Interaction):
        """Display current swear filter settings."""
        embed = discord.Embed(
            title="🤬 Swear Filter Settings",
            description="Configure word filtering and automatic responses",
            color=discord.Color.red()
        )

        words_display = "\n".join(f"• `{word}`" for word in self.words[:10])
        if len(self.words) > 10:
            words_display += f"\n... and {len(self.words) - 10} more"

        embed.add_field(
            name="Filtered Words",
            value=words_display or "No words configured",
            inline=False
        )

        embed.add_field(
            name="Action",
            value=f"**Action:** {self.action.title()}\n" +
                  (f"**Timeout Duration:** {self.timeout_duration//60} minutes" if self.action == "timeout" else ""),
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class WatchChannelsView(discord.ui.View):
    """Channel monitoring configuration."""

    def __init__(self):
        super().__init__(timeout=300)
        self.watched_channels = []

    async def load_settings(self, guild_id: int, bot):
        """Load watched channels settings."""
        try:
            from utils.cache import get_config
            config = await get_config(bot, guild_id, "watched_channels", [])
            self.watched_channels = config
        except (AttributeError, TypeError, ValueError) as e:
            # Use defaults if loading fails
            self.watched_channels = []

    async def save_settings(self, guild_id: int, bot):
        """Save watched channels settings."""
        try:
            from utils.cache import set_config
            await set_config(bot, guild_id, "watched_channels", self.watched_channels)
        except (AttributeError, TypeError, ValueError) as e:
            raise commands.CommandError(f"Failed to save watched channels: {str(e)}")

    async def show_settings(self, interaction: discord.Interaction):
        """Display watched channels."""
        embed = discord.Embed(
            title="👁️ Watched Channels",
            description="Channels that are monitored for rule violations",
            color=discord.Color.blue()
        )

        if not self.watched_channels:
            embed.add_field(
                name="No Channels Watched",
                value="Click 'Add Channel' to start monitoring channels",
                inline=False
            )
        else:
            channels_list = []
            for channel_id in self.watched_channels:
                channel = interaction.guild.get_channel(int(channel_id))
                channel_name = channel.mention if channel else f"Deleted Channel ({channel_id})"
                channels_list.append(channel_name)

            embed.add_field(
                name="Currently Watched",
                value="\n".join(channels_list[:20]) + ("\n..." if len(channels_list) > 20 else ""),
                inline=False
            )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class StaffExemptionsView(discord.ui.View):
    """Staff exemption configuration."""

    def __init__(self):
        super().__init__(timeout=300)
        self.staff_roles = []

    async def load_settings(self, guild_id: int, bot):
        """Load staff exemption settings."""
        try:
            from utils.cache import get_config
            config = await get_config(bot, guild_id, "staff_exemptions", [])
            self.staff_roles = config
        except (AttributeError, TypeError, ValueError) as e:
            # Use defaults if loading fails
            self.staff_roles = []

    async def save_settings(self, guild_id: int, bot):
        """Save staff exemption settings."""
        try:
            from utils.cache import set_config
            await set_config(bot, guild_id, "staff_exemptions", self.staff_roles)
        except (AttributeError, TypeError, ValueError) as e:
            raise commands.CommandError(f"Failed to save staff exemptions: {str(e)}")

    async def show_settings(self, interaction: discord.Interaction):
        """Display staff exemptions."""
        embed = discord.Embed(
            title="🛡️ Staff Exemptions",
            description="Roles that are exempt from automatic moderation",
            color=discord.Color.green()
        )

        if not self.staff_roles:
            embed.add_field(
                name="No Exempt Roles",
                value="Click 'Add Role' to exempt staff roles from moderation",
                inline=False
            )
        else:
            roles_list = []
            for role_id in self.staff_roles:
                role = interaction.guild.get_role(int(role_id))
                role_name = role.mention if role else f"Deleted Role ({role_id})"
                roles_list.append(role_name)

            embed.add_field(
                name="Exempt Roles",
                value="\n".join(roles_list[:20]) + ("\n..." if len(roles_list) > 20 else ""),
                inline=False
            )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class IncidentLogView(discord.ui.View):
    """View recent moderation incidents."""

    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.incidents: List[ModerationIncident] = []

    async def show_incidents(self, interaction: discord.Interaction):
        """Show recent moderation incidents."""
        # Load recent incidents
        async with get_session() as session:
            result = await session.execute(
                select(ModerationIncident)
                .where(ModerationIncident.guild_id == interaction.guild_id)
                .order_by(ModerationIncident.created_at.desc())
                .limit(50)
            )
            self.incidents = result.scalars().all()

        if not self.incidents:
            embed = discord.Embed(
                title="📋 Recent Incidents",
                description="No moderation incidents recorded.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = self._create_incidents_embed(interaction)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    def _create_incidents_embed(self, interaction: discord.Interaction):
        """Create embed showing incidents."""
        embed = discord.Embed(
            title="📋 Recent Moderation Incidents",
            description=f"Showing {len(self.incidents)} recent incidents",
            color=discord.Color.orange()
        )

        for incident in self.incidents[:10]:  # Show first 10
            user = interaction.guild.get_member(incident.user_id)
            user_name = user.display_name if user else f"Unknown User ({incident.user_id})"

            moderator = interaction.guild.get_member(incident.moderator_id) if incident.moderator_id else None
            moderator_name = moderator.display_name if moderator else "Automatic"

            embed.add_field(
                name=f"{incident.type.title()} - {incident.action.title()}",
                value=(
                    f"**User:** {user_name}\n"
                    f"**Moderator:** {moderator_name}\n"
                    f"**Action:** {incident.action_taken or incident.action}\n"
                    f"**Time:** {discord.utils.format_dt(incident.created_at, 'R')}"
                ),
                inline=True
            )

        return embed


# FIXED: Added missing ReportMessageModal
class ReportMessageModal(discord.ui.Modal):
    """Modal for reporting messages."""

    def __init__(self):
        super().__init__(title="Report a Message")

        self.message_link = discord.ui.TextInput(
            label="Message Link",
            placeholder="Right-click message → Copy Message Link",
            required=True
        )
        self.add_item(self.message_link)

        self.reason = discord.ui.TextInput(
            label="Reason for Report",
            placeholder="Why are you reporting this message?",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle report submission."""
        try:
            # Parse message link
            link = self.message_link.value.strip()
            if not link.startswith("https://discord.com/channels/"):
                embed = discord.Embed(
                    title="❌ Invalid Link",
                    description="Please provide a valid Discord message link.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Extract channel and message IDs from link
            parts = link.replace("https://discord.com/channels/", "").split("/")
            if len(parts) != 3:
                raise ValueError("Invalid link format")

            guild_id, channel_id, message_id = parts
            channel_id = int(channel_id)
            message_id = int(message_id)

            # Create moderation log entry
            async with get_session() as session:
                log_entry = ModerationLog(
                    guild_id=interaction.guild_id,
                    moderator_id=interaction.user.id,
                    target_user_id=0,  # Will be updated when moderator reviews
                    action_type="report",
                    reason=self.reason.value,
                    message_snapshot={
                        "link": link,
                        "channel_id": channel_id,
                        "message_id": message_id,
                        "reported_by": interaction.user.id
                    },
                    action_taken="report_submitted"
                )
                session.add(log_entry)
                await session.commit()

            embed = discord.Embed(
                title="✅ Report Submitted",
                description="Your report has been submitted to the moderation team. Thank you for helping keep the server safe!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Next Steps",
                value="Moderators will review your report and take appropriate action if needed.",
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (ValueError, IndexError) as e:
            embed = discord.Embed(
                title="❌ Invalid Link",
                description="Please provide a valid Discord message link.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to submit report: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# FIXED: Added missing UserRoleManagerView
class UserRoleManagerView(discord.ui.View):
    """View for managing a user's roles."""

    def __init__(self, target_user: discord.Member):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.available_roles = []
        self.selected_roles = []

    async def show_role_manager(self, interaction: discord.Interaction):
        """Show the role management interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get available roles (excluding @everyone, managed roles, and higher roles)
        bot_member = interaction.guild.me
        self.available_roles = [
            role for role in interaction.guild.roles
            if role != interaction.guild.default_role  # Skip @everyone
            and not role.managed  # Skip bot/integration roles
            and role < bot_member.top_role  # Skip roles above bot
            and role < interaction.user.top_role  # Skip roles above user
        ]

        # Get current roles
        self.selected_roles = [
            role.id for role in self.target_user.roles
            if role in self.available_roles
        ]

        embed = discord.Embed(
            title=f"🎭 Manage Roles - {self.target_user.display_name}",
            description="Select roles to add or remove",
            color=discord.Color.blue()
        )

        current_roles = [
            interaction.guild.get_role(role_id) for role_id in self.selected_roles
        ]
        current_roles = [role for role in current_roles if role]

        if current_roles:
            embed.add_field(
                name="Current Roles",
                value="\n".join(role.mention for role in current_roles[:10]),
                inline=False
            )
        else:
            embed.add_field(
                name="Current Roles",
                value="No special roles assigned",
                inline=False
            )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Add Roles", style=discord.ButtonStyle.green, emoji="➕") # type: ignore[arg-type]
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add roles to the user."""
        available_to_add = [
            role for role in self.available_roles
            if role.id not in self.selected_roles
        ]

        if not available_to_add:
            await interaction.response.send_message("No roles available to add.", ephemeral=True)
            return

        # Create select menu with available roles
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"Add {role.name} to {self.target_user.display_name}"
            )
            for role in available_to_add[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Select roles to add...",
            options=options,
            min_values=1,
            max_values=min(len(options), 10)
        )
        select.callback = self._handle_add_roles

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select roles to add:", view=view, ephemeral=True)

    async def _handle_add_roles(self, interaction: discord.Interaction):
        """Handle adding selected roles."""
        try:
            role_ids = [int(value) for value in interaction.data['values']]
            roles_to_add = [interaction.guild.get_role(role_id) for role_id in role_ids]
            roles_to_add = [role for role in roles_to_add if role]

            await self.target_user.add_roles(*roles_to_add, reason=f"Added by {interaction.user}")

            embed = discord.Embed(
                title="✅ Roles Added",
                description=f"Added {len(roles_to_add)} role(s) to {self.target_user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Added Roles",
                value="\n".join(role.mention for role in roles_to_add),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.Forbidden, discord.HTTPException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to add roles: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remove Roles", style=discord.ButtonStyle.red, emoji="➖") # type: ignore[arg-type]
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove roles from the user."""
        current_roles = [
            interaction.guild.get_role(role_id) for role_id in self.selected_roles
        ]
        current_roles = [role for role in current_roles if role]

        if not current_roles:
            await interaction.response.send_message("No roles to remove.", ephemeral=True)
            return

        # Create select menu with current roles
        options = [
            discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"Remove {role.name} from {self.target_user.display_name}"
            )
            for role in current_roles[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Select roles to remove...",
            options=options,
            min_values=1,
            max_values=min(len(options), 10)
        )
        select.callback = self._handle_remove_roles

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select roles to remove:", view=view, ephemeral=True)

    async def _handle_remove_roles(self, interaction: discord.Interaction):
        """Handle removing selected roles."""
        try:
            role_ids = [int(value) for value in interaction.data['values']]
            roles_to_remove = [interaction.guild.get_role(role_id) for role_id in role_ids]
            roles_to_remove = [role for role in roles_to_remove if role]

            await self.target_user.remove_roles(*roles_to_remove, reason=f"Removed by {interaction.user}")

            embed = discord.Embed(
                title="✅ Roles Removed",
                description=f"Removed {len(roles_to_remove)} role(s) from {self.target_user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Removed Roles",
                value="\n".join(role.mention for role in roles_to_remove),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.Forbidden, discord.HTTPException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove roles: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# FIXED: Added AdminTestingView for admin testing functionality
class AdminTestingView(discord.ui.View):
    """Admin testing tools."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_testing_options(self, interaction: discord.Interaction):
        """Show admin testing options."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access admin testing",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="🧪 Admin Testing Tools",
            description="Test bot functionality without needing separate accounts",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="Available Tests",
            value=(
                "• **Test Onboarding** - Simulate the onboarding process\n"
                "• **Test Server Join** - Simulate a new member joining\n"
                "• **Test Moderation** - Simulate moderation actions\n"
                "• **Test Permissions** - Check permission settings"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Test Onboarding", style=discord.ButtonStyle.primary, emoji="👋") # type: ignore[arg-type]
    async def test_onboarding(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Test the onboarding process as an admin."""
        try:
            # Create a test onboarding session
            async with get_session() as session:
                # Check if admin already has a test session
                existing = await session.execute(
                    select(OnboardingSession).where(
                        and_(
                            OnboardingSession.guild_id == interaction.guild_id,
                            OnboardingSession.user_id == interaction.user.id,
                            OnboardingSession.state == 'admin_test'
                        )
                    )
                )
                test_session = existing.scalar_one_or_none()

                if not test_session:
                    # Create new test session
                    test_session = OnboardingSession(
                        guild_id=interaction.guild_id,
                        user_id=interaction.user.id,
                        state='admin_test',
                        answers={},
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(test_session)
                    await session.commit()
                else:
                    # Reset existing test session
                    await session.execute(
                        update(OnboardingSession)
                        .where(OnboardingSession.id == test_session.id)
                        .values(
                            answers={},
                            created_at=datetime.now(timezone.utc),
                            state='admin_test'
                        )
                    )
                    await session.commit()

            # Start onboarding process
            from views.onboarding import OnboardingView
            view = OnboardingView(is_admin_test=True)
            await view.start_onboarding(interaction)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to start test onboarding: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Test Server Join", style=discord.ButtonStyle.secondary, emoji="📥") # type: ignore[arg-type]
    async def test_server_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Simulate a server join event."""
        try:
            # Simulate the on_member_join event logic
            from bot import GuildBot

            embed = discord.Embed(
                title="✅ Server Join Test",
                description="Simulating new member join process...",
                color=discord.Color.green()
            )

            embed.add_field(
                name="What would happen:",
                value=(
                    f"• Welcome message sent to welcome channel\n"
                    f"• Member assigned default role (if configured)\n"
                    f"• Onboarding prompt displayed\n"
                    f"• Member added to pending queue"
                ),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (AttributeError, TypeError) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to simulate server join: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Clean Test Data", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def clean_test_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clean up admin test data."""
        try:
            async with get_session() as session:
                # Delete admin test sessions
                await session.execute(
                    select(OnboardingSession).where(
                        and_(
                            OnboardingSession.guild_id == interaction.guild_id,
                            OnboardingSession.user_id == interaction.user.id,
                            OnboardingSession.state == 'admin_test'
                        )
                    ).execution_options(synchronize_session=False)
                )
                await session.commit()

            embed = discord.Embed(
                title="✅ Test Data Cleaned",
                description="All admin test data has been removed.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to clean test data: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)