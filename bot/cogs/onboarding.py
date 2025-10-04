# File: cogs/onboarding.py
# Location: /bot/cogs/onboarding.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

from models import (
    Guild, Member, Question, QuestionOption, Submission, Answer, Appeal,
    ApplicationStatus, QuestionType, AppealStatus
)
from database import db
from utils.helpers import (
    get_or_create_guild, get_or_create_member, create_embed,
    try_send_dm, get_channel_id
)

logger = logging.getLogger(__name__)


class OnboardingCog(commands.Cog):
    """Handles member onboarding and application process"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Greet new members and invite them to apply"""
        if member.bot:
            return

        await get_or_create_guild(member.guild.id, member.guild.name)

        embed = await create_embed(
            title="Welcome to the Server!",
            description=(
                f"Hello {member.mention}! Welcome to **{member.guild.name}**.\n\n"
                "To get started, please complete our application process using `/apply`.\n"
                "This helps us get to know you better and ensures a great community experience."
            ),
            color=discord.Color.green()
        )

        dm_sent = await try_send_dm(member, embed=embed)

        if not dm_sent:
            channel_id = await get_channel_id(member.guild.id, "welcome")
            if channel_id:
                channel = member.guild.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

    @app_commands.command(name="apply", description="Start or continue your application")
    @app_commands.guild_only()
    async def apply(self, interaction: discord.Interaction):
        """Start or resume application process"""
        member_record = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        if not member_record:
            await interaction.response.send_message(
                "❌ Server not configured. Please contact an administrator.",
                ephemeral=True
            )
            return

        if member_record.blacklisted:
            await interaction.response.send_message(
                "❌ You are not permitted to use this bot.",
                ephemeral=True
            )
            return

        if member_record.status == ApplicationStatus.APPROVED:
            await interaction.response.send_message(
                "✅ You're already approved! Welcome to the community.",
                ephemeral=True
            )
            return

        if member_record.status == ApplicationStatus.PENDING:
            await interaction.response.send_message(
                "⏳ Your application is pending review. Please wait for a moderator to process it.",
                ephemeral=True
            )
            return

        if member_record.status == ApplicationStatus.REJECTED:
            await interaction.response.send_message(
                "❌ Your application was rejected. Please use `/appeal` to submit an appeal.",
                ephemeral=True
            )
            return

        await self._start_application(interaction, member_record)

    async def _start_application(self, interaction: discord.Interaction, member: Member):
        """Begin the application flow"""
        with db.session_scope() as session:
            # Get fresh member data
            member = session.query(Member).filter_by(id=member.id).first()

            # If member status is IN_PROGRESS, they can start/continue
            if member.status != ApplicationStatus.IN_PROGRESS:
                last_status = session.query(Submission.status) \
                    .filter_by(member_id=member.id) \
                    .order_by(Submission.id.desc()) \
                    .limit(1).scalar()

                if last_status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED, ApplicationStatus.PENDING):
                    await self._send_response(
                        interaction,
                        "❌ You cannot start a new application. If rejected, use `/appeal`.",
                        ephemeral=True
                    )
                    return

            submission = session.query(Submission).filter_by(
                member_id=member.id,
                status=ApplicationStatus.IN_PROGRESS
            ).first()

            if not submission:
                submission = Submission(
                    member_id=member.id,
                    status=ApplicationStatus.IN_PROGRESS
                )
                session.add(submission)
                session.flush()

            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            questions = session.query(Question).filter_by(
                guild_id=guild.id,
                active=True,
                parent_question_id=None
            ).order_by(Question.order).all()

            if not questions:
                await self._send_response(
                    interaction,
                    "❌ No application questions configured. Please contact an administrator.",
                    ephemeral=True
                )
                return

            answered_ids = {a.question_id for a in submission.answers}
            next_question = None

            for q in questions:
                if q.id not in answered_ids:
                    next_question = q
                    break

            if not next_question:
                await self._submit_application(interaction, submission)
                return

            await self._present_question(interaction, submission.id, next_question)

    async def _present_question(
            self,
            interaction: discord.Interaction,
            submission_id: int,
            question: Question
    ):
        """Present a question to the user"""
        if question.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
            view = QuestionView(
                self.bot,
                submission_id,
                question,
                is_multi=question.question_type == QuestionType.MULTI_CHOICE
            )

            embed = await create_embed(
                title="Application Question",
                description=question.question_text,
                color=discord.Color.blue(),
                footer="Select your answer below"
            )

            await self._send_response(interaction, embed=embed, view=view, ephemeral=True)

        else:
            if not interaction.response.is_done():
                modal = QuestionModal(
                    submission_id,
                    question,
                    question.question_type
                )
                await interaction.response.send_modal(modal)

    async def _submit_application(self, interaction: discord.Interaction, submission: Submission):
        """Submit completed application for review"""
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission.id).first()
            submission.status = ApplicationStatus.PENDING
            submission.submitted_at = datetime.utcnow()
            submission.member.status = ApplicationStatus.PENDING

            flagged = False
            flag_reason = []

            for answer in submission.answers:
                for option in answer.selected_options:
                    if option.immediate_reject:
                        flagged = True
                        flag_reason.append(f"Selected: {option.option_text}")

            if flagged:
                submission.flagged = True
                submission.flag_reason = "; ".join(flag_reason)

            session.commit()

        await self._send_to_moderators(interaction.guild.id, submission.id)

        embed = await create_embed(
            title="Application Submitted!",
            description=(
                "Thank you for completing your application.\n\n"
                "Our moderation team will review it shortly. "
                "You'll be notified once a decision has been made."
            ),
            color=discord.Color.green()
        )

        await self._send_response(interaction, embed=embed, ephemeral=True)

    async def _send_to_moderators(self, guild_id: int, submission_id: int):
        """Post application to moderator queue"""
        channel_id = await get_channel_id(guild_id, "moderator_queue")
        if not channel_id:
            logger.warning(f"No moderator queue channel configured for guild {guild_id}")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            member = submission.member

            embed = discord.Embed(
                title="📋 New Application",
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

            embed.set_footer(text=f"Submission ID: {submission_id}")

            view = ModReviewView(self.bot, submission_id)
            await channel.send(embed=embed, view=view)

    @app_commands.command(name="appeal", description="Submit an appeal if your application was rejected")
    @app_commands.guild_only()
    async def appeal(self, interaction: discord.Interaction):
        """Allow a rejected member to submit an appeal"""
        member_record = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        if not member_record or member_record.status != ApplicationStatus.REJECTED:
            await interaction.response.send_message(
                "⚠️ You can only appeal if your application has been rejected.",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            member = session.query(Member).filter_by(id=member_record.id).first()

            if member.appeal_count >= 1:
                await interaction.response.send_message(
                    "❌ You have already submitted an appeal. You cannot submit another.",
                    ephemeral=True
                )
                return

            pending_appeal = session.query(Appeal).filter_by(
                member_id=member.id,
                status=AppealStatus.PENDING
            ).first()

            if pending_appeal:
                await interaction.response.send_message(
                    "⏳ You already have a pending appeal. Please wait for a moderator to review it.",
                    ephemeral=True
                )
                return

        modal = AppealModal(member_record.id)
        await interaction.response.send_modal(modal)

    async def _send_response(self, interaction, content=None, embed=None, view=None, ephemeral=False):
        """Helper to send response or followup based on interaction state"""
        kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)


class QuestionView(discord.ui.View):
    """Interactive view for answering choice questions"""

    def __init__(self, bot, submission_id: int, question: Question, is_multi: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.submission_id = submission_id
        self.question = question

        options = [
            discord.SelectOption(
                label=opt.option_text[:100],
                value=str(opt.id)
            )
            for opt in question.options
        ]

        select = discord.ui.Select(
            placeholder="Choose your answer...",
            options=options,
            min_values=1,
            max_values=len(options) if is_multi else 1
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle answer selection"""
        selected_ids = [int(val) for val in interaction.data['values']]

        with db.session_scope() as session:
            answer = session.query(Answer).filter_by(
                submission_id=self.submission_id,
                question_id=self.question.id
            ).first()

            if not answer:
                answer = Answer(
                    submission_id=self.submission_id,
                    question_id=self.question.id
                )
                session.add(answer)
                session.flush()

            answer.selected_options = []

            for opt_id in selected_ids:
                option = session.query(QuestionOption).filter_by(id=opt_id).first()
                if option:
                    answer.selected_options.append(option)

            session.commit()

            if any(opt.immediate_reject for opt in answer.selected_options):
                submission = session.query(Submission).filter_by(id=self.submission_id).first()
                submission.status = ApplicationStatus.REJECTED
                submission.flagged = True
                submission.flag_reason = "Immediate reject option selected"
                submission.member.status = ApplicationStatus.REJECTED
                session.commit()

                await interaction.response.send_message(
                    "❌ Your application has been rejected based on your response.",
                    ephemeral=True
                )
                return

            submission = session.query(Submission).filter_by(id=self.submission_id).first()
            member_id = submission.member.id

        with db.session_scope() as session:
            member = session.query(Member).filter_by(id=member_id).first()

        onboarding_cog = self.bot.get_cog('OnboardingCog')
        if onboarding_cog:
            await onboarding_cog._start_application(interaction, member)


class QuestionModal(discord.ui.Modal):
    """Modal for text/numeric questions"""

    def __init__(self, submission_id: int, question: Question, question_type: QuestionType):
        super().__init__(title="Application Question")
        self.submission_id = submission_id
        self.question = question
        self.question_type = question_type

        style = discord.TextStyle.long if question_type == QuestionType.LONG_TEXT else discord.TextStyle.short

        self.answer_input = discord.ui.TextInput(
            label=question.question_text[:45],
            placeholder="Enter your answer...",
            style=style,
            required=question.required,
            max_length=4000 if question_type == QuestionType.LONG_TEXT else 1000
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Save answer and continue"""
        value = self.answer_input.value

        with db.session_scope() as session:
            answer = session.query(Answer).filter_by(
                submission_id=self.submission_id,
                question_id=self.question.id
            ).first()

            if not answer:
                answer = Answer(
                    submission_id=self.submission_id,
                    question_id=self.question.id
                )
                session.add(answer)

            if self.question_type == QuestionType.NUMERIC:
                try:
                    answer.numeric_answer = int(value)
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Please enter a valid number.",
                        ephemeral=True
                    )
                    return
            else:
                answer.text_answer = value

            session.commit()

            submission = session.query(Submission).filter_by(id=self.submission_id).first()
            member_id = submission.member.id

        with db.session_scope() as session:
            member = session.query(Member).filter_by(id=member_id).first()

        from bot import OnboardingBot
        bot = interaction.client
        onboarding_cog = bot.get_cog('OnboardingCog')
        if onboarding_cog:
            await onboarding_cog._start_application(interaction, member)


class AppealModal(discord.ui.Modal):
    """Modal for appeal submission"""

    def __init__(self, member_id: int):
        super().__init__(title="Appeal Application Rejection")
        self.member_id = member_id

        self.reason = discord.ui.TextInput(
            label="Why should we reconsider?",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000,
            placeholder="Explain why you believe your application should be reconsidered..."
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        """Submit appeal"""
        with db.session_scope() as session:
            member = session.query(Member).filter_by(id=self.member_id).first()

            appeal = Appeal(
                member_id=member.id,
                reason=str(self.reason.value),
                status=AppealStatus.PENDING
            )
            session.add(appeal)
            member.appeal_count += 1
            session.commit()

            appeal_id = appeal.id
            user_id = member.user_id

        channel_id = await get_channel_id(interaction.guild.id, "moderator_queue")
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="📨 Appeal Submitted",
                    color=discord.Color.gold()
                )
                embed.add_field(
                    name="User",
                    value=f"<@{user_id}>",
                    inline=False
                )
                embed.add_field(
                    name="Reason",
                    value=self.reason.value,
                    inline=False
                )
                embed.set_footer(text=f"Appeal ID: {appeal_id}")

                view = AppealReviewView(interaction.client, appeal_id)
                await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            "✅ Your appeal has been submitted. A moderator will review it.",
            ephemeral=True
        )


class AppealReviewView(discord.ui.View):
    """View for moderators to review appeals"""

    def __init__(self, bot, appeal_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.appeal_id = appeal_id

    @discord.ui.button(label="✅ Approve Appeal", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve the appeal"""
        with db.session_scope() as session:
            appeal = session.query(Appeal).filter_by(id=self.appeal_id).first()
            if not appeal:
                await interaction.response.send_message("❌ Appeal not found.", ephemeral=True)
                return

            if appeal.status != AppealStatus.PENDING:
                await interaction.response.send_message("❌ This appeal has already been processed.", ephemeral=True)
                return

            member = appeal.member

            appeal.status = AppealStatus.APPROVED
            appeal.reviewed_at = datetime.utcnow()
            appeal.reviewer_id = interaction.user.id

            # Reset member status to allow reapplication
            member.status = ApplicationStatus.IN_PROGRESS
            member.blacklisted = False
            member.blacklist_reason = None

            # Delete ALL old submissions to give them a fresh start
            session.query(Submission).filter_by(member_id=member.id).delete()

            session.commit()
            user_id = member.user_id

        discord_user = await self.bot.fetch_user(user_id)
        if discord_user:
            embed = await create_embed(
                title="✅ Appeal Approved",
                description=(
                    "Your appeal has been approved! You may now reapply to the server using `/apply`.\n\n"
                    "Please take this opportunity to submit a complete and thoughtful application."
                ),
                color=discord.Color.green()
            )
            await try_send_dm(discord_user, embed=embed)

        await interaction.response.send_message(
            f"✅ Appeal approved for <@{user_id}>. They can now reapply.",
            ephemeral=True
        )

    @discord.ui.button(label="❌ Reject Appeal", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reject the appeal"""
        modal = AppealRejectModal(self.bot, self.appeal_id)
        await interaction.response.send_modal(modal)


class AppealRejectModal(discord.ui.Modal):
    """Modal for rejecting appeal with reason"""

    def __init__(self, bot, appeal_id: int):
        super().__init__(title="Reject Appeal")
        self.bot = bot
        self.appeal_id = appeal_id

        self.note = discord.ui.TextInput(
            label="Note (optional)",
            placeholder="Internal note about why appeal was rejected...",
            style=discord.TextStyle.long,
            required=False,
            max_length=500
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        """Process appeal rejection"""
        with db.session_scope() as session:
            appeal = session.query(Appeal).filter_by(id=self.appeal_id).first()
            if not appeal:
                await interaction.response.send_message("❌ Appeal not found.", ephemeral=True)
                return

            appeal.status = AppealStatus.REJECTED
            appeal.reviewed_at = datetime.utcnow()
            appeal.reviewer_id = interaction.user.id
            appeal.reviewer_note = self.note.value

            member = appeal.member
            member.blacklisted = True
            if not member.blacklist_reason:
                member.blacklist_reason = "Appeal rejected"

            session.commit()
            user_id = member.user_id

        discord_user = await self.bot.fetch_user(user_id)
        if discord_user:
            embed = await create_embed(
                title="Appeal Decision",
                description="Your appeal has been reviewed and was not approved.",
                color=discord.Color.red()
            )
            await try_send_dm(discord_user, embed=embed)

        await interaction.response.send_message(
            f"✅ Appeal rejected for <@{user_id}>.",
            ephemeral=True
        )


class ModReviewView(discord.ui.View):
    """View for moderator review actions"""

    def __init__(self, bot, submission_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.submission_id = submission_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green, custom_id="approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve application"""
        from cogs.moderation import ModerationCog
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.show_approve_options(interaction, self.submission_id)

    @discord.ui.button(label="❌ Reject", style=discord.ButtonStyle.red, custom_id="reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reject application"""
        modal = RejectModal(self.bot, self.submission_id)
        await interaction.response.send_modal(modal)


class RejectModal(discord.ui.Modal):
    """Modal for rejection with reason"""

    def __init__(self, bot, submission_id: int):
        super().__init__(title="Reject Application")
        self.bot = bot
        self.submission_id = submission_id

        self.reason = discord.ui.TextInput(
            label="Reason for rejection",
            placeholder="Enter reason (optional)...",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        from cogs.moderation import ModerationCog
        mod_cog = self.bot.get_cog('ModerationCog')
        if mod_cog:
            await mod_cog.reject_application(
                interaction,
                self.submission_id,
                self.reason.value,
                ban=False
            )


async def setup(bot):
    await bot.add_cog(OnboardingCog(bot))