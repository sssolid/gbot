# File: cogs/moderation.py
# Location: /bot/cogs/moderation.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
import logging

from models import (
    Guild, Member, Submission, ModeratorAction, Configuration,
    ApplicationStatus, ActionType, RoleTier
)
from database import db
from utils.helpers import (
    create_embed, try_send_dm, get_channel_id, get_role_id
)
from utils.checks import require_moderator, can_moderate_submission

logger = logging.getLogger(__name__)


class ModerationCog(commands.Cog):
    """Handles moderation review and decision workflows"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="View pending applications")
    @app_commands.guild_only()
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

            # Create queue embed
            embed = discord.Embed(
                title="📋 Pending Applications",
                description=f"**{len(pending)}** application(s) awaiting review",
                color=discord.Color.blue()
            )

            for sub in pending[:10]:  # Show first 10
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

            # Create detailed review embed
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

            # Add all answers
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

            # Add action buttons
            view = ReviewActionView(self.bot, submission_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def approve_application(self, interaction: discord.Interaction, submission_id: int):
        """Approve an application"""
        if not await can_moderate_submission(interaction.guild.id, interaction.user.id, submission_id):
            await interaction.response.send_message(
                "❌ This application cannot be moderated.",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                await interaction.response.send_message("❌ Submission not found.", ephemeral=True)
                return

            member = submission.member

            # Update submission status
            submission.status = ApplicationStatus.APPROVED
            submission.reviewed_at = datetime.utcnow()
            submission.reviewer_id = interaction.user.id

            # Update member status
            member.status = ApplicationStatus.APPROVED
            member.approved_at = datetime.utcnow()

            # Log action
            action = ModeratorAction(
                submission_id=submission.id,
                moderator_id=interaction.user.id,
                action_type=ActionType.APPROVE
            )
            session.add(action)
            session.commit()

            guild_id = interaction.guild.id
            user_id = member.user_id

        # Assign member role
        member_role_id = await get_role_id(interaction.guild.id, RoleTier.MEMBER)
        if member_role_id:
            role = interaction.guild.get_role(member_role_id)
            discord_member = interaction.guild.get_member(user_id)
            if role and discord_member:
                try:
                    await discord_member.add_roles(role, reason="Application approved")
                except discord.Forbidden:
                    logger.error(f"Cannot assign role {member_role_id} to user {user_id}")

        # Send notification to user
        discord_user = await self.bot.fetch_user(user_id)
        if discord_user:
            embed = await create_embed(
                title="✅ Application Approved!",
                description=(
                    f"Congratulations! Your application to **{interaction.guild.name}** has been approved.\n\n"
                    "You now have access to the server. Welcome to the community!\n\n"
                    "You can use `/character add` to add your game characters."
                ),
                color=discord.Color.green()
            )
            await try_send_dm(discord_user, embed=embed)

        # Post announcement
        await self._post_welcome_announcement(interaction.guild.id, user_id)

        # Confirm to moderator
        await interaction.response.send_message(
            f"✅ Application approved for <@{user_id}>",
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
        if not await can_moderate_submission(interaction.guild.id, interaction.user.id, submission_id):
            await interaction.response.send_message(
                "❌ This application cannot be moderated.",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            if not submission:
                await interaction.response.send_message("❌ Submission not found.", ephemeral=True)
                return

            member = submission.member

            # Update submission
            submission.status = ApplicationStatus.REJECTED
            submission.reviewed_at = datetime.utcnow()
            submission.reviewer_id = interaction.user.id
            submission.rejection_reason = reason

            # Update member
            member.status = ApplicationStatus.REJECTED

            if ban:
                member.blacklisted = True
                member.blacklist_reason = reason or "Application rejected with ban"

            # Log action
            action = ModeratorAction(
                submission_id=submission.id,
                moderator_id=interaction.user.id,
                action_type=ActionType.BAN if ban else ActionType.REJECT,
                reason=reason,
                banned=ban
            )
            session.add(action)
            session.commit()

            user_id = member.user_id

        # Notify user
        discord_user = await self.bot.fetch_user(user_id)
        if discord_user and not ban:
            embed = await create_embed(
                title="Application Decision",
                description=(
                    f"Your application to **{interaction.guild.name}** was not approved at this time.\n\n"
                    f"{f'Reason: {reason}' if reason else 'No specific reason provided.'}"
                ),
                color=discord.Color.orange()
            )
            await try_send_dm(discord_user, embed=embed)

        # Optionally ban from server
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

        # Confirm to moderator
        ban_text = " and banned" if ban else ""
        await interaction.response.send_message(
            f"✅ Application rejected{ban_text} for <@{user_id}>",
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

        # Get welcome template
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=guild_id).first()
            config = session.query(Configuration).filter_by(guild_id=guild.id).first()

            if not config or not config.announcement_enabled:
                return

            template = config.welcome_template or "Welcome {mention} to the server!"

        # Replace template variables
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
            await mod_cog.approve_application(interaction, self.submission_id)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RejectDecisionModal(self.bot, self.submission_id)
        await interaction.response.send_modal(modal)


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
        # Ask about ban
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