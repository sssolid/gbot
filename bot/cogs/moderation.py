# File: cogs/moderation.py
# Location: /bot/cogs/moderation.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta
import logging

from models import (
    Guild, Member, Submission, ModeratorAction, Configuration, RoleRegistry,
    ApplicationStatus, ActionType, RoleTier
)
from database import db
from utils.helpers import (
    create_embed, try_send_dm, get_channel_id, get_role_id
)

logger = logging.getLogger(__name__)


class ModerationCog(commands.Cog):
    """Handles moderation review and decision workflows"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="View pending applications")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def queue(self, interaction: discord.Interaction):
        """View moderation queue"""
        if not await self._check_moderator(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            pending = session.query(Submission).join(Member).filter(
                Member.guild_id == guild.id,
                Submission.status == ApplicationStatus.PENDING
            ).order_by(Submission.submitted_at).all()

            if not pending:
                await interaction.response.send_message(
                    "📭 No pending applications.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 Pending Applications",
                description=f"**{len(pending)}** application(s) awaiting review",
                color=discord.Color.blue()
            )

            for sub in pending[:10]:
                member = sub.member
                flag_emoji = "⚠️ " if sub.flagged else ""
                submitted = sub.submitted_at.strftime("%Y-%m-%d %H:%M UTC") if sub.submitted_at else "Unknown"

                embed.add_field(
                    name=f"{flag_emoji}ID: {sub.id}",
                    value=f"<@{member.user_id}>\nSubmitted: {submitted}",
                    inline=True
                )

            if len(pending) > 10:
                embed.set_footer(text=f"Showing 10 of {len(pending)} applications")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="review", description="Review a specific application")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(submission_id="The ID of the submission to review")
    async def review(self, interaction: discord.Interaction, submission_id: int):
        """Review a specific application"""
        if not await self._check_moderator(interaction):
            return

        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()

            if not submission:
                await interaction.response.send_message(
                    "❌ Submission not found.",
                    ephemeral=True
                )
                return

            if submission.status not in [ApplicationStatus.PENDING, ApplicationStatus.FLAGGED]:
                await interaction.response.send_message(
                    f"❌ This application has already been {submission.status.value}.",
                    ephemeral=True
                )
                return

            member = submission.member
            embed = discord.Embed(
                title="📋 Application Review",
                color=discord.Color.orange() if submission.flagged else discord.Color.blue()
            )

            embed.add_field(
                name="Applicant",
                value=f"<@{member.user_id}> ({member.username})",
                inline=False
            )

            if submission.flagged:
                embed.add_field(
                    name="⚠️ FLAGGED",
                    value=submission.flag_reason or "Immediate reject option selected",
                    inline=False
                )

            for answer in submission.answers:
                question = answer.question
                if answer.text_answer:
                    value = answer.text_answer[:1024]
                elif answer.numeric_answer is not None:
                    value = str(answer.numeric_answer)
                elif answer.selected_options:
                    value = ", ".join([opt.option_text for opt in answer.selected_options])
                else:
                    value = "No answer"

                embed.add_field(
                    name=question.question_text[:256],
                    value=value,
                    inline=False
                )

            submitted = submission.submitted_at.strftime("%Y-%m-%d %H:%M UTC") if submission.submitted_at else "Unknown"
            embed.set_footer(text=f"Submission ID: {submission_id} | Submitted: {submitted}")

            view = ReviewActionView(self.bot, submission_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_approve_options(self, interaction: discord.Interaction, submission_id: int):
        """Show role selection for approval"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            roles = session.query(RoleRegistry).filter_by(guild_id=guild.id).order_by(
                RoleRegistry.hierarchy_level.desc()
            ).all()

            if not roles:
                await interaction.response.send_message(
                    "❌ No roles configured. Use `/set_role` first.",
                    ephemeral=True
                )
                return

            view = RoleSelectView(self.bot, submission_id, roles)
            await interaction.response.send_message(
                "Select the role to assign to this member:",
                view=view,
                ephemeral=True
            )

    async def approve_application(self, interaction: discord.Interaction, submission_id: int, role_tier: RoleTier):
        """Approve an application with specified role"""
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                await interaction.response.send_message("❌ Submission not found.", ephemeral=True)
                return

            member = submission.member

            submission.status = ApplicationStatus.APPROVED
            submission.reviewed_at = datetime.utcnow()
            submission.reviewer_id = interaction.user.id

            member.status = ApplicationStatus.APPROVED
            member.approved_at = datetime.utcnow()

            action = ModeratorAction(
                submission_id=submission.id,
                target_user_id=member.user_id,
                moderator_id=interaction.user.id,
                action_type=ActionType.APPROVE,
                reason=f"Approved with {role_tier.value} role"
            )
            session.add(action)
            session.commit()

            guild_id = interaction.guild.id
            user_id = member.user_id

        role_id = await get_role_id(interaction.guild.id, role_tier)
        if role_id:
            role = interaction.guild.get_role(role_id)
            discord_member = interaction.guild.get_member(user_id)
            if role and discord_member:
                try:
                    await discord_member.add_roles(role, reason="Application approved")
                except discord.Forbidden:
                    logger.error(f"Cannot assign role {role_id} to user {user_id}")

        discord_user = await self.bot.fetch_user(user_id)
        if discord_user:
            embed = await create_embed(
                title="✅ Application Approved!",
                description=(
                    f"Congratulations! Your application to **{interaction.guild.name}** has been approved.\n\n"
                    "You now have access to the server. Welcome to the community!\n\n"
                    "You can use `/character_add` to add your game characters."
                ),
                color=discord.Color.green()
            )
            await try_send_dm(discord_user, embed=embed)

        await self._post_welcome_announcement(interaction.guild.id, user_id)

        await interaction.response.send_message(
            f"✅ Application approved for <@{user_id}> with {role_tier.value} role",
            ephemeral=True
        )

    async def reject_application(
            self,
            interaction: discord.Interaction,
            submission_id: int,
            reason: str = None,
            ban: bool = False
    ):
        """Reject an application"""
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                await interaction.response.send_message("❌ Submission not found.", ephemeral=True)
                return

            member = submission.member

            submission.status = ApplicationStatus.REJECTED
            submission.reviewed_at = datetime.utcnow()
            submission.reviewer_id = interaction.user.id
            submission.rejection_reason = reason

            member.status = ApplicationStatus.REJECTED

            if ban:
                member.blacklisted = True
                member.blacklist_reason = reason or "Application rejected with ban"

            action = ModeratorAction(
                submission_id=submission.id,
                target_user_id=member.user_id,
                moderator_id=interaction.user.id,
                action_type=ActionType.BAN if ban else ActionType.REJECT,
                reason=reason,
                banned=ban
            )
            session.add(action)
            session.commit()

            user_id = member.user_id

        discord_user = await self.bot.fetch_user(user_id)
        if discord_user and not ban:
            embed = await create_embed(
                title="Application Decision",
                description=(
                    f"Your application to **{interaction.guild.name}** was not approved at this time.\n\n"
                    f"{f'Reason: {reason}' if reason else 'No specific reason provided.'}\n\n"
                    "You may submit an appeal using `/appeal`."
                ),
                color=discord.Color.orange()
            )
            await try_send_dm(discord_user, embed=embed)

        if ban:
            discord_member = interaction.guild.get_member(user_id)
            if discord_member:
                try:
                    await discord_member.ban(
                        reason=f"Application rejected: {reason or 'Policy violation'}",
                        delete_message_days=0
                    )
                except discord.Forbidden:
                    logger.error(f"Cannot ban user {user_id}")

        ban_text = " and banned" if ban else ""
        await interaction.response.send_message(
            f"✅ Application rejected{ban_text} for <@{user_id}>",
            ephemeral=True
        )

    @app_commands.command(name="promote", description="Promote a member to a higher role")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to promote",
        role="The role to promote them to"
    )
    async def promote(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Promote a member"""
        if not await self._check_moderator(interaction):
            return

        try:
            await member.add_roles(role, reason=f"Promoted by {interaction.user.name}")

            with db.session_scope() as session:
                action = ModeratorAction(
                    target_user_id=member.id,
                    moderator_id=interaction.user.id,
                    action_type=ActionType.PROMOTE,
                    reason=f"Promoted to {role.name}"
                )
                session.add(action)

            announcement_channel_id = await get_channel_id(interaction.guild.id, "announcements")
            if announcement_channel_id:
                channel = interaction.guild.get_channel(announcement_channel_id)
                if channel:
                    embed = await create_embed(
                        title="🎉 Member Promoted!",
                        description=f"Congratulations to {member.mention} on their promotion to {role.mention}!",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)

            await interaction.response.send_message(
                f"✅ Successfully promoted {member.mention} to {role.mention}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to manage this role.",
                ephemeral=True
            )

    @app_commands.command(name="demote", description="Demote a member by removing a role")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to demote",
        role="The role to remove"
    )
    async def demote(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Demote a member"""
        if not await self._check_moderator(interaction):
            return

        try:
            await member.remove_roles(role, reason=f"Demoted by {interaction.user.name}")

            with db.session_scope() as session:
                action = ModeratorAction(
                    target_user_id=member.id,
                    moderator_id=interaction.user.id,
                    action_type=ActionType.DEMOTE,
                    reason=f"Removed {role.name}"
                )
                session.add(action)

            await interaction.response.send_message(
                f"✅ Removed {role.mention} from {member.mention}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to manage this role.",
                ephemeral=True
            )

    @app_commands.command(name="mod_kick", description="Kick a member from the server")
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for kicking"
    )
    async def mod_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        """Kick a member"""
        if not await self._check_moderator(interaction):
            return

        try:
            with db.session_scope() as session:
                action = ModeratorAction(
                    target_user_id=member.id,
                    moderator_id=interaction.user.id,
                    action_type=ActionType.KICK,
                    reason=reason
                )
                session.add(action)

            await member.kick(reason=reason or "No reason provided")

            await interaction.response.send_message(
                f"✅ Kicked {member.mention}\nReason: {reason or 'No reason provided'}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to kick this member.",
                ephemeral=True
            )

    @app_commands.command(name="mod_ban", description="Ban a member from the server")
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for banning",
        delete_messages="Days of messages to delete (0-7)"
    )
    async def mod_ban(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = None,
            delete_messages: int = 0
    ):
        """Ban a member"""
        if not await self._check_moderator(interaction):
            return

        if delete_messages < 0 or delete_messages > 7:
            await interaction.response.send_message(
                "❌ Delete messages must be between 0 and 7 days.",
                ephemeral=True
            )
            return

        try:
            with db.session_scope() as session:
                db_member = session.query(Member).filter_by(
                    user_id=member.id,
                    guild_id=session.query(Guild).filter_by(guild_id=interaction.guild.id).first().id
                ).first()

                if db_member:
                    db_member.blacklisted = True
                    db_member.blacklist_reason = reason

                action = ModeratorAction(
                    target_user_id=member.id,
                    moderator_id=interaction.user.id,
                    action_type=ActionType.BAN,
                    reason=reason,
                    banned=True
                )
                session.add(action)

            await member.ban(reason=reason or "No reason provided", delete_message_days=delete_messages)

            await interaction.response.send_message(
                f"✅ Banned {member.mention}\nReason: {reason or 'No reason provided'}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to ban this member.",
                ephemeral=True
            )

    @app_commands.command(name="mod_timeout", description="Timeout a member")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration in minutes",
        reason="Reason for timeout"
    )
    async def mod_timeout(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            duration: int,
            reason: str = None
    ):
        """Timeout a member"""
        if not await self._check_moderator(interaction):
            return

        if duration < 1 or duration > 40320:  # Max 28 days
            await interaction.response.send_message(
                "❌ Duration must be between 1 minute and 28 days (40320 minutes).",
                ephemeral=True
            )
            return

        try:
            timeout_until = datetime.utcnow() + timedelta(minutes=duration)

            with db.session_scope() as session:
                action = ModeratorAction(
                    target_user_id=member.id,
                    moderator_id=interaction.user.id,
                    action_type=ActionType.TIMEOUT,
                    reason=f"{reason or 'No reason'} ({duration}m)"
                )
                session.add(action)

            await member.timeout(timeout_until, reason=reason or "No reason provided")

            await interaction.response.send_message(
                f"✅ Timed out {member.mention} for {duration} minutes\nReason: {reason or 'No reason provided'}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to timeout this member.",
                ephemeral=True
            )

    async def _post_welcome_announcement(self, guild_id: int, user_id: int):
        """Post welcome announcement to configured channel"""
        channel_id = await get_channel_id(guild_id, "announcements")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=guild_id).first()
            config = session.query(Configuration).filter_by(guild_id=guild.id).first()

            if not config or not config.announcement_enabled:
                return

            template = config.welcome_template or "Welcome {mention} to the server!"

        message = template.replace("{mention}", f"<@{user_id}>")

        embed = await create_embed(
            title="🎉 New Member!",
            description=message,
            color=discord.Color.green()
        )

        await channel.send(embed=embed)

    async def _check_moderator(self, interaction: discord.Interaction) -> bool:
        """Check if user has moderator permissions"""
        from utils.checks import is_moderator
        if not await is_moderator(interaction):
            await interaction.response.send_message(
                "❌ You need moderator permissions to use this command.",
                ephemeral=True
            )
            return False
        return True


class ReviewActionView(discord.ui.View):
    """Action buttons for application review"""

    def __init__(self, bot, submission_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.submission_id = submission_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.show_approve_options(interaction, self.submission_id)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RejectDecisionModal(self.bot, self.submission_id)
        await interaction.response.send_modal(modal)


class RoleSelectView(discord.ui.View):
    """View for selecting role on approval"""

    def __init__(self, bot, submission_id: int, roles: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.submission_id = submission_id

        options = [
            discord.SelectOption(
                label=role.role_tier.value.title(),
                value=role.role_tier.value,
                description=f"Hierarchy level {role.hierarchy_level}"
            )
            for role in roles
        ]

        select = discord.ui.Select(
            placeholder="Choose a role...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        role_tier_str = interaction.data['values'][0]
        role_tier = RoleTier(role_tier_str)

        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.approve_application(interaction, self.submission_id, role_tier)


class RejectDecisionModal(discord.ui.Modal):
    """Modal for rejection decision"""

    def __init__(self, bot, submission_id: int):
        super().__init__(title="Reject Application")
        self.bot = bot
        self.submission_id = submission_id

        self.reason = discord.ui.TextInput(
            label="Reason (optional)",
            placeholder="Enter rejection reason...",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        view = BanConfirmView(self.bot, self.submission_id, self.reason.value)
        await interaction.response.send_message(
            "Should this user be banned from the server?",
            view=view,
            ephemeral=True
        )


class BanConfirmView(discord.ui.View):
    """Confirm ban decision"""

    def __init__(self, bot, submission_id: int, reason: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.submission_id = submission_id
        self.reason = reason

    @discord.ui.button(label="Reject Only", style=discord.ButtonStyle.secondary)
    async def reject_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.reject_application(interaction, self.submission_id, self.reason, ban=False)

    @discord.ui.button(label="Reject & Ban", style=discord.ButtonStyle.danger)
    async def reject_and_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.reject_application(interaction, self.submission_id, self.reason, ban=True)


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))