# File: cogs/onboarding.py
# Location: /bot/cogs/onboarding.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

from sqlalchemy.orm import joinedload

from models import (
    Guild, Member, Question, QuestionOption, Submission, Answer, Appeal,
    ApplicationStatus, QuestionType, AppealStatus, SubmissionType, RoleTier
)
from database import db
from utils.helpers import (
    get_or_create_guild, get_or_create_member, create_embed,
    try_send_dm, get_channel_id, get_role_id
)

logger = logging.getLogger(__name__)


class OnboardingCog(commands.Cog):
    """Handles member onboarding and application process"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send DM with onboarding options when member joins"""
        if member.bot:
            return

        guild_id = member.guild.id
        guild_name = member.guild.name

        await get_or_create_guild(guild_id, guild_name)
        await get_or_create_member(guild_id, member.id, member.name)

        embed = await create_embed(
            title=f"Welcome to {guild_name}!",
            description=(
                "Thank you for joining our community! Please select how you'd like to proceed:\n\n"
                "**🛡️ Apply to Join** - Complete an application to become a full member\n"
                "**🤝 Friend/Ally** - You're from another guild or know someone here\n"
                "**👤 Regular User** - Just here to hang out, no application needed"
            ),
            color=discord.Color.blue()
        )

        view = OnboardingChoiceView(self.bot, guild_id)
        dm_sent = await try_send_dm(member, embed=embed, view=view)

        if not dm_sent:
            channel_id = await get_channel_id(member.guild.id, "welcome")
            if channel_id:
                channel = member.guild.get_channel(channel_id)
                if channel:
                    await channel.send(
                        f"{member.mention}, please check your DMs to complete onboarding! "
                        "If you can't receive DMs, please enable them and rejoin.",
                        delete_after=60
                    )

    async def start_application(self, interaction: discord.Interaction, member: Member, guild_id: int):
        """Begin the application flow"""
        with db.session_scope() as session:
            member = session.query(Member).filter_by(id=member.id).first()

            submission = (
                session.query(Submission)
                .options(joinedload(Submission.answers))  # 👈 eager-load answers
                .filter_by(
                    member_id=member.id,
                    status=ApplicationStatus.IN_PROGRESS,
                    submission_type=SubmissionType.APPLICANT,
                )
                .first()
            )

            if not submission:
                submission = Submission(
                    member_id=member.id,
                    status=ApplicationStatus.IN_PROGRESS,
                    submission_type=SubmissionType.APPLICANT,
                )
                session.add(submission)
                session.flush()
                session.refresh(submission)

            # Set APPLICANT role - get guild from bot
            guild = self.bot.get_guild(guild_id)
            if guild:
                applicant_role_id = await get_role_id(guild_id, RoleTier.APPLICANT)
                if applicant_role_id:
                    applicant_role = guild.get_role(applicant_role_id)
                    discord_member = guild.get_member(interaction.user.id)
                    if applicant_role and discord_member:
                        try:
                            await discord_member.add_roles(applicant_role, reason="Started application")
                            member.role_tier = RoleTier.APPLICANT
                        except discord.Forbidden:
                            logger.error(f"Cannot assign applicant role to {interaction.user.id}")

            guild_db = session.query(Guild).filter_by(guild_id=guild_id).first()
            questions = session.query(Question).filter_by(
                guild_id=guild_db.id,
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

            answers = session.query(Answer).filter_by(submission_id=submission.id).all()
            answered_ids = {a.question_id for a in answers}
            next_question = None

            for q in questions:
                if q.id not in answered_ids:
                    next_question = q
                    break

            # If no root questions left, check for conditional questions
            if not next_question:
                next_question = await self._get_next_conditional_question(session, submission)

            if not next_question:
                await self._submit_application(interaction, submission, guild_id)
                return

            await self._present_question(interaction, submission.id, next_question, guild_id)

    async def _get_next_conditional_question(self, session, submission):
        """Get next conditional question based on answers"""
        answers = (
            session.query(Answer)
            .options(joinedload(Answer.selected_options))
            .filter_by(submission_id=submission.id)
            .all()
        )

        for answer in answers:
            if answer.selected_options:
                for option in answer.selected_options:
                    conditional = session.query(Question).filter_by(
                        parent_option_id=option.id,
                        active=True
                    ).first()

                    if conditional:
                        already_answered = session.query(Answer).filter_by(
                            submission_id=submission.id,
                            question_id=conditional.id
                        ).first()

                        if not already_answered:
                            return conditional
        return None

    async def _present_question(
            self,
            interaction: discord.Interaction,
            submission_id: int,
            question: Question,
            guild_id: int
    ):
        """Present a question to the user"""
        if question.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTI_CHOICE]:
            view = QuestionView(
                self.bot,
                submission_id,
                question,
                guild_id,
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
                    self.bot,
                    submission_id,
                    question,
                    guild_id,
                    question.question_type
                )
                await interaction.response.send_modal(modal)

    async def _submit_application(self, interaction: discord.Interaction, submission: Submission, guild_id: int):
        """Submit completed application for review"""
        with db.session_scope() as session:
            submission = session.query(Submission).filter_by(id=submission.id).first()
            submission.status = ApplicationStatus.PENDING
            submission.submitted_at = datetime.utcnow()
            submission.member.status = ApplicationStatus.PENDING

            flagged = False
            flag_reason = []

            answers = (
                session.query(Answer)
                .options(joinedload(Answer.selected_options))
                .filter_by(submission_id=submission.id)
                .all()
            )

            for answer in answers:
                for option in answer.selected_options:
                    if option.immediate_reject:
                        flagged = True
                        flag_reason.append(f"Selected: {option.option_text}")

            if flagged:
                submission.flagged = True
                submission.flag_reason = "; ".join(flag_reason)

            session.commit()

        await self._send_to_moderators(guild_id, submission.id)

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

            if submission.submission_type == SubmissionType.FRIEND:
                embed = discord.Embed(
                    title="🤝 New Friend/Ally Request",
                    color=discord.Color.gold()
                )
                embed.add_field(
                    name="User",
                    value=f"<@{member.user_id}> ({member.username})",
                    inline=False
                )
                embed.add_field(
                    name="Information",
                    value=submission.friend_info[:1024],
                    inline=False
                )
            else:
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

    async def _send_response(self, interaction, content=None, embed=None, view=None, ephemeral=False):
        """Helper to send response or followup based on interaction state"""
        kwargs = {"content": content, "embed": embed, "ephemeral": ephemeral}
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)


class OnboardingChoiceView(discord.ui.View):
    """View for initial onboarding choice"""

    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="🛡️ Apply to Join", style=discord.ButtonStyle.primary, custom_id="apply")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start application process"""
        member_record = await get_or_create_member(
            self.guild_id,
            interaction.user.id,
            interaction.user.name
        )

        if member_record.blacklisted:
            await interaction.response.send_message(
                "❌ You are not permitted to apply.",
                ephemeral=True
            )
            return

        onboarding_cog = self.bot.get_cog('OnboardingCog')
        if onboarding_cog:
            await onboarding_cog.start_application(interaction, member_record, self.guild_id)

    @discord.ui.button(label="🤝 Friend/Ally", style=discord.ButtonStyle.secondary, custom_id="friend")
    async def friend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Friend/Ally path"""
        member_record = await get_or_create_member(
            self.guild_id,
            interaction.user.id,
            interaction.user.name
        )

        if member_record.blacklisted:
            await interaction.response.send_message(
                "❌ You are not permitted to join as a friend.",
                ephemeral=True
            )
            return

        modal = FriendModal(self.bot, self.guild_id, member_record.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👤 Regular User", style=discord.ButtonStyle.secondary, custom_id="regular")
    async def regular_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Regular user - no onboarding needed"""
        await interaction.response.send_message(
            "✅ Welcome! You're all set. Feel free to explore the server!",
            ephemeral=True
        )


class FriendModal(discord.ui.Modal):
    """Modal for friend/ally information"""

    def __init__(self, bot, guild_id: int, member_id: int):
        super().__init__(title="Friend/Ally Information")
        self.bot = bot
        self.guild_id = guild_id
        self.member_id = member_id

        self.info = discord.ui.TextInput(
            label="Tell us about yourself",
            placeholder="Who are you? What guild are you from? Who do you know here?",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        """Submit friend request"""
        with db.session_scope() as session:
            submission = Submission(
                member_id=self.member_id,
                submission_type=SubmissionType.FRIEND,
                friend_info=self.info.value,
                status=ApplicationStatus.PENDING,
                submitted_at=datetime.utcnow()
            )
            session.add(submission)

            member = session.query(Member).filter_by(id=self.member_id).first()
            member.status = ApplicationStatus.PENDING

            session.commit()
            submission_id = submission.id

        onboarding_cog = self.bot.get_cog('OnboardingCog')
        if onboarding_cog:
            await onboarding_cog._send_to_moderators(self.guild_id, submission_id)

        embed = await create_embed(
            title="✅ Request Submitted",
            description=(
                "Thank you! Your friend/ally request has been submitted.\n\n"
                "A moderator will review it and get back to you soon."
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuestionView(discord.ui.View):
    """Interactive view for answering choice questions"""

    def __init__(self, bot, submission_id: int, question: Question, guild_id: int, is_multi: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.submission_id = submission_id
        self.question = question
        self.guild_id = guild_id

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
            await onboarding_cog.start_application(interaction, member, self.guild_id)


class QuestionModal(discord.ui.Modal):
    """Modal for text/numeric questions"""

    def __init__(self, bot, submission_id: int, question: Question, guild_id: int, question_type: QuestionType):
        super().__init__(title="Application Question")
        self.bot = bot
        self.submission_id = submission_id
        self.question = question
        self.guild_id = guild_id
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

        onboarding_cog = self.bot.get_cog('OnboardingCog')
        if onboarding_cog:
            await onboarding_cog.start_application(interaction, member, self.guild_id)


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