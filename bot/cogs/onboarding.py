# File: cogs/onboarding.py
# Location: /bot/cogs/onboarding.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
import logging

from models import (
    Guild, Member, Question, QuestionOption, Submission, Answer,
    ApplicationStatus, QuestionType
)
from database import db
from utils.helpers import (
    get_or_create_guild, get_or_create_member, create_embed,
    try_send_dm, get_channel_id
)
from utils.checks import require_not_blacklisted

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
            # Try to send in a welcome channel if configured
            channel_id = await get_channel_id(member.guild.id, "welcome")
            if channel_id:
                channel = member.guild.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)

    @app_commands.command(name="apply", description="Start or continue your application")
    @app_commands.guild_only()
    async def apply(self, interaction: discord.Interaction):
        """Start or resume application process"""
        if await self._check_blacklist(interaction):
            return

        # Get or create member record
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

        # Check current status
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

        # Start or resume application
        await self._start_application(interaction, member_record)

    async def _start_application(self, interaction: discord.Interaction, member: Member):
        """Begin the application flow"""
        with db.session_scope() as session:
            # Get existing submission or create new
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

            # Get first unanswered question
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            questions = session.query(Question).filter_by(
                guild_id=guild.id,
                active=True,
                parent_question_id=None
            ).order_by(Question.order).all()

            if not questions:
                await interaction.response.send_message(
                    "❌ No application questions configured. Please contact an administrator.",
                    ephemeral=True
                )
                return

            # Find first unanswered question
            answered_ids = {a.question_id for a in submission.answers}
            next_question = None

            for q in questions:
                if q.id not in answered_ids:
                    next_question = q
                    break

            print("Next question:", next_question.question_text if next_question else "None")

            if not next_question:
                # All questions answered, submit
                await self._submit_application(interaction, submission)
                return

            # Present question
            await self._present_question(interaction, submission.id, next_question)

    async def _present_question(
            self,
            interaction: discord.Interaction,
            submission_id: int,
            question: Question
    ):
        """Present a question to the user"""

        if question.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
            # Use select menu for choices
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

            # await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await (interaction.followup.send if interaction.response.is_done() else interaction.response.send_message)(
                embed=embed, view=view, ephemeral=True)

        else:
            # Use modal for text/numeric input
            modal = QuestionModal(
                submission_id,
                question,
                question.question_type
            )
            await (interaction.response.send_modal(QuestionModal(submission_id, question,
                                                                 question.question_type)) if not interaction.response.is_done() else interaction.followup.send(
                "⚠️ Cannot open modal after first response.", ephemeral=True))

    async def _submit_application(self, interaction: discord.Interaction, submission: Submission):
        """Submit completed application for review"""
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission.id).first()
            submission.status = ApplicationStatus.PENDING
            submission.submitted_at = datetime.utcnow()

            # Check for immediate reject flags
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

        # Send to moderator queue
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

            # Create review embed
            embed = discord.Embed(
                title="📋 New Application",
                color=discord.Color.orange() if submission.flagged else discord.Color.blue()
            )

            guild = self.bot.get_guild(guild_id)
            user = guild.get_member(member.user_id) if guild else None

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

            # Add answers
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

    async def _check_blacklist(self, interaction: discord.Interaction) -> bool:
        """Check if user is blacklisted"""
        from utils.helpers import is_blacklisted
        if await is_blacklisted(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                "❌ You are not permitted to use this bot.",
                ephemeral=True
            )
            return True
        return False


class QuestionView(discord.ui.View):
    """Interactive view for answering choice questions"""

    def __init__(self, bot, submission_id: int, question: Question, is_multi: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.submission_id = submission_id
        self.question = question

        # Add select menu
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

        # Save answer
        with db.session_scope() as session:
            # Check if answer exists
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

            # Clear existing selections
            answer.selected_options = []

            # Add new selections
            for opt_id in selected_ids:
                option = session.query(QuestionOption).filter_by(id=opt_id).first()
                if option:
                    answer.selected_options.append(option)

            session.commit()

        # Continue to next question
        await interaction.response.send_message(
            "✅ Answer saved! Loading next question...",
            ephemeral=True
        )

        # Get member and continue
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=self.submission_id).first()
            member = submission.member

        onboarding_cog = self.bot.get_cog('OnboardingCog')
        await onboarding_cog._start_application(interaction, member)


class QuestionModal(discord.ui.Modal):
    """Modal for text/numeric questions"""

    def __init__(self, submission_id: int, question: Question, question_type: QuestionType):
        super().__init__(title="Application Question")
        self.submission_id = submission_id
        self.question = question
        self.question_type = question_type

        # Add input field
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

        await interaction.response.send_message(
            "✅ Answer saved! Loading next question...",
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
            await mod_cog.approve_application(interaction, self.submission_id)

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