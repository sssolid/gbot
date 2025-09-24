"""
Onboarding system views for the Guild Management Bot - FIXED VERSION
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import discord
from sqlalchemy import select, and_, update, desc
from discord.ext import commands

from database import OnboardingQuestion, OnboardingSession, OnboardingRule, User, get_session
from utils.permissions import PermissionChecker


class OnboardingView(discord.ui.View):
    """Main onboarding interface for new members."""

    def __init__(self, is_admin_test: bool = False):
        super().__init__(timeout=None)  # Persistent view
        self.questions: List[OnboardingQuestion] = []
        self.current_question = 0
        self.answers: Dict[str, Any] = {}
        self.session_id: Optional[int] = None
        self.user_timezone: Optional[str] = None
        self.is_admin_test = is_admin_test  # FIXED: Added admin testing support

    async def start_onboarding(self, interaction: discord.Interaction):
        """Start the onboarding process."""
        try:
            # Load questions
            await self.load_questions(interaction.guild_id)

            if not self.questions:
                embed = discord.Embed(
                    title="❌ No Questions Available",
                    description="No onboarding questions have been configured for this server.",
                    color=discord.Color.red()
                )
                if PermissionChecker.is_admin(interaction.user):
                    embed.add_field(
                        name="Administrator Note",
                        value="Configure onboarding questions through the Admin Dashboard → Configuration → Onboarding Questions.",
                        inline=False
                    )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Load or create session
            await self.load_session(interaction.user.id, interaction.guild_id)

            # Show first question
            await self.show_current_question(interaction)

        except (AttributeError, TypeError, ValueError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Configuration Error",
                description="There was an issue with the onboarding configuration. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to start onboarding: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def load_questions(self, guild_id: int):
        """Load active onboarding questions."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion)
                .where(
                    and_(
                        OnboardingQuestion.guild_id == guild_id,
                        OnboardingQuestion.is_active == True
                    )
                )
                .order_by(OnboardingQuestion.position)
            )
            self.questions = result.scalars().all()

    async def load_session(self, user_id: int, guild_id: int):
        """Load existing onboarding session or create new one."""
        async with get_session() as session:
            # Check for existing session
            session_state = 'admin_test' if self.is_admin_test else 'in_progress'

            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.guild_id == guild_id,
                        OnboardingSession.user_id == user_id,
                        OnboardingSession.state == session_state
                    )
                )
                .order_by(OnboardingSession.created_at.desc())
                .limit(1)
            )
            existing_session = result.scalar_one_or_none()

            if existing_session:
                self.session_id = existing_session.id
                self.answers = existing_session.answers or {}
                self.user_timezone = existing_session.user_timezone

                # Find current question based on answered questions
                answered_qids = set(self.answers.keys())
                for i, question in enumerate(self.questions):
                    if question.qid not in answered_qids:
                        self.current_question = i
                        break
                else:
                    self.current_question = len(self.questions)
            else:
                # Create new session
                new_session = OnboardingSession(
                    guild_id=guild_id,
                    user_id=user_id,
                    state=session_state,
                    answers={},
                    created_at=datetime.now(timezone.utc)
                )
                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)

                self.session_id = new_session.id
                self.answers = {}
                self.current_question = 0

    async def show_current_question(self, interaction: discord.Interaction):
        """Display the current question."""
        if self.current_question >= len(self.questions):
            await self.complete_onboarding(interaction)
            return

        question = self.questions[self.current_question]

        # Create question embed
        embed = discord.Embed(
            title="📋 Server Onboarding" + (" (Admin Test)" if self.is_admin_test else ""),
            description=question.prompt,
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Progress",
            value=f"Question {self.current_question + 1} of {len(self.questions)}",
            inline=True
        )

        if question.required:
            embed.add_field(
                name="Required",
                value="✅ This question is required",
                inline=True
            )

        # Create appropriate UI based on question type
        view = self._create_question_view(question)

        if hasattr(interaction.response, 'is_done') and interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _create_question_view(self, question: OnboardingQuestion):
        """Create UI view for the current question type."""
        if question.type == "single_select":
            return SingleSelectQuestionView(self, question)
        elif question.type == "text":
            return TextQuestionView(self, question)
        elif question.type == "timezone":
            return TimezoneQuestionView(self, question)
        else:
            return TextQuestionView(self, question)  # Default to text

    async def save_answer(self, qid: str, answer: Any):
        """Save answer to database."""
        self.answers[qid] = answer

        async with get_session() as session:
            await session.execute(
                update(OnboardingSession)
                .where(OnboardingSession.id == self.session_id)
                .values(answers=self.answers)
            )
            await session.commit()

    async def next_question(self, interaction: discord.Interaction):
        """Move to the next question."""
        self.current_question += 1
        await self.show_current_question(interaction)

    async def complete_onboarding(self, interaction: discord.Interaction):
        """Complete the onboarding process."""
        try:
            # Apply role suggestion rules
            suggested_roles = await self.apply_role_rules(interaction.guild_id)

            # Update session status
            completion_state = 'admin_test_complete' if self.is_admin_test else 'completed'

            async with get_session() as session:
                await session.execute(
                    update(OnboardingSession)
                    .where(OnboardingSession.id == self.session_id)
                    .values(
                        state=completion_state,
                        suggestion={"roles": suggested_roles} if suggested_roles else None,
                        completed_at=datetime.now(timezone.utc),
                        user_timezone=self.user_timezone
                    )
                )
                await session.commit()

            # Create completion embed
            embed = discord.Embed(
                title="✅ Onboarding Complete" + (" (Test)" if self.is_admin_test else ""),
                description="Thank you for completing the onboarding process!",
                color=discord.Color.green()
            )

            if self.is_admin_test:
                embed.add_field(
                    name="🧪 Admin Test Complete",
                    value="This was a test run of the onboarding process. No actual roles were assigned.",
                    inline=False
                )

                embed.add_field(
                    name="Test Results",
                    value=f"**Questions Answered:** {len(self.answers)}\n**Suggested Roles:** {len(suggested_roles) if suggested_roles else 0}",
                    inline=True
                )

                if suggested_roles:
                    role_names = []
                    for role_id in suggested_roles:
                        role = interaction.guild.get_role(role_id)
                        role_names.append(role.mention if role else f"Unknown Role ({role_id})")

                    embed.add_field(
                        name="Would Suggest These Roles",
                        value="\n".join(role_names[:10]),
                        inline=False
                    )
            else:
                embed.add_field(
                    name="What's Next?",
                    value=(
                        "Your application will be reviewed by server administrators. "
                        "You'll receive a role assignment once approved!"
                    ),
                    inline=False
                )

                if suggested_roles:
                    embed.add_field(
                        name="Suggested Roles",
                        value=f"{len(suggested_roles)} role(s) have been suggested based on your answers.",
                        inline=True
                    )

            embed.add_field(
                name="Your Answers",
                value=f"Recorded {len(self.answers)} response(s)",
                inline=True
            )

            await interaction.edit_original_response(embed=embed, view=None)

        except (AttributeError, TypeError, ValueError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Completion Error",
                description="There was an issue completing your onboarding. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to complete onboarding: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)

    async def apply_role_rules(self, guild_id: int) -> List[int]:
        """Apply role suggestion rules based on answers."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(OnboardingRule)
                    .where(
                        and_(
                            OnboardingRule.guild_id == guild_id,
                            OnboardingRule.is_active == True
                        )
                    )
                )
                rules = result.scalars().all()

            suggested_role_ids = []

            for rule in rules:
                # Check if all conditions are met
                conditions_met = True
                for condition in rule.when_conditions:
                    qid = condition.get('key')
                    expected_value = condition.get('value')

                    if qid not in self.answers or self.answers[qid] != expected_value:
                        conditions_met = False
                        break

                if conditions_met:
                    # Add suggested roles
                    for role_identifier in rule.suggest_roles:
                        if isinstance(role_identifier, int):
                            suggested_role_ids.append(role_identifier)
                        elif isinstance(role_identifier, str):
                            # Try to find role by name
                            # This would need the guild object, so we'll skip name-based for now
                            pass

            return list(set(suggested_role_ids))  # Remove duplicates

        except (AttributeError, TypeError, ValueError):
            # FIXED: More specific exception handling for rule processing
            return []


class SingleSelectQuestionView(discord.ui.View):
    """View for single-select questions."""

    def __init__(self, onboarding_view: OnboardingView, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.onboarding_view = onboarding_view
        self.question = question

        # Create select menu
        if question.options and len(question.options) > 0:
            options = [
                discord.SelectOption(
                    label=option[:100],  # Discord limit
                    value=str(i),
                    description=f"Select {option}"[:100]
                )
                for i, option in enumerate(question.options[:25])  # Discord limit
            ]

            select = discord.ui.Select(
                placeholder="Choose an option...",
                options=options
            )
            select.callback = self.handle_selection
            self.add_item(select)

    async def handle_selection(self, interaction: discord.Interaction):
        """Handle option selection."""
        try:
            selected_index = int(interaction.data['values'][0])
            selected_option = self.question.options[selected_index]

            # Save answer
            await self.onboarding_view.save_answer(self.question.qid, selected_option)

            # Move to next question
            await self.onboarding_view.next_question(interaction)

        except (ValueError, IndexError, KeyError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Selection Error",
                description="There was an issue with your selection. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to process selection: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class TextQuestionView(discord.ui.View):
    """View for text input questions."""

    def __init__(self, onboarding_view: OnboardingView, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.onboarding_view = onboarding_view
        self.question = question

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.primary, emoji="✏️") # type: ignore[arg-type]
    async def answer_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open text input modal."""
        modal = TextAnswerModal(self.onboarding_view, self.question)
        await interaction.response.send_modal(modal)


class TextAnswerModal(discord.ui.Modal):
    """Modal for text answer input."""

    def __init__(self, onboarding_view: OnboardingView, question: OnboardingQuestion):
        super().__init__(title="Answer Question")
        self.onboarding_view = onboarding_view
        self.question = question

        self.answer_input = discord.ui.TextInput(
            label=question.prompt[:45] + "..." if len(question.prompt) > 45 else question.prompt,
            placeholder="Enter your answer here...",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=question.required,
            max_length=1000
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle text answer submission."""
        try:
            answer = self.answer_input.value.strip()

            if self.question.required and not answer:
                embed = discord.Embed(
                    title="❌ Answer Required",
                    description="This question requires an answer. Please try again.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Save answer
            await self.onboarding_view.save_answer(self.question.qid, answer)

            # Move to next question
            await self.onboarding_view.next_question(interaction)

        except (AttributeError, TypeError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Input Error",
                description="There was an issue with your answer. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to save answer: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class TimezoneQuestionView(discord.ui.View):
    """View for timezone selection."""

    def __init__(self, onboarding_view: OnboardingView, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.onboarding_view = onboarding_view
        self.question = question

        # Common timezone options
        timezone_options = [
            discord.SelectOption(label="Eastern Time (EST/EDT)", value="America/New_York"),
            discord.SelectOption(label="Central Time (CST/CDT)", value="America/Chicago"),
            discord.SelectOption(label="Mountain Time (MST/MDT)", value="America/Denver"),
            discord.SelectOption(label="Pacific Time (PST/PDT)", value="America/Los_Angeles"),
            discord.SelectOption(label="Alaska Time (AKST/AKDT)", value="America/Anchorage"),
            discord.SelectOption(label="Hawaii Time (HST)", value="Pacific/Honolulu"),
            discord.SelectOption(label="Greenwich Mean Time (GMT)", value="Europe/London"),
            discord.SelectOption(label="Central European Time (CET)", value="Europe/Berlin"),
            discord.SelectOption(label="Eastern European Time (EET)", value="Europe/Kiev"),
            discord.SelectOption(label="Japan Standard Time (JST)", value="Asia/Tokyo"),
            discord.SelectOption(label="Australian Eastern Time (AEST)", value="Australia/Sydney"),
            discord.SelectOption(label="Other/Prefer not to say", value="other"),
        ]

        select = discord.ui.Select(
            placeholder="Select your timezone...",
            options=timezone_options
        )
        select.callback = self.handle_timezone_selection
        self.add_item(select)

    async def handle_timezone_selection(self, interaction: discord.Interaction):
        """Handle timezone selection."""
        try:
            selected_timezone = interaction.data['values'][0]

            # Save timezone to onboarding view
            self.onboarding_view.user_timezone = selected_timezone

            # Save answer
            await self.onboarding_view.save_answer(self.question.qid, selected_timezone)

            # Move to next question
            await self.onboarding_view.next_question(interaction)

        except (KeyError, AttributeError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Timezone Error",
                description="There was an issue with your timezone selection. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to save timezone: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class OnboardingStartView(discord.ui.View):
    """Simple view to start onboarding."""

    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @discord.ui.button(
        label="Start Onboarding",
        style=discord.ButtonStyle.primary, # type: ignore[arg-type]
        emoji="👋",
        custom_id="start_onboarding"
    )
    async def start_onboarding(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the onboarding process."""
        # Check if user has already completed onboarding
        try:
            async with get_session() as session:
                existing_session = await session.execute(
                    select(OnboardingSession)
                    .where(
                        and_(
                            OnboardingSession.guild_id == interaction.guild_id,
                            OnboardingSession.user_id == interaction.user.id,
                            OnboardingSession.state.in_(['completed', 'approved'])
                        )
                    )
                    .order_by(OnboardingSession.created_at.desc())
                    .limit(1)
                )
                completed_session = existing_session.scalar_one_or_none()

                if completed_session:
                    embed = discord.Embed(
                        title="ℹ️ Already Completed",
                        description="You have already completed the onboarding process for this server.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="Status",
                        value="Approved" if completed_session.state == 'approved' else "Pending Review",
                        inline=True
                    )
                    embed.add_field(
                        name="Completed",
                        value=discord.utils.format_dt(completed_session.completed_at, 'R'),
                        inline=True
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            # Start new onboarding
            view = OnboardingView()
            await view.start_onboarding(interaction)

        except (AttributeError, TypeError, ValueError) as e:
            # FIXED: More specific exception handling
            embed = discord.Embed(
                title="❌ Configuration Error",
                description="There was an issue starting onboarding. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to start onboarding: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class OnboardingQueueView(discord.ui.View):
    """Admin view for managing onboarding queue."""

    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.pending_sessions: List[OnboardingSession] = []

    async def show_queue(self, interaction: discord.Interaction):
        """Show the onboarding queue."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view onboarding queue",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.load_pending_sessions(interaction.guild_id)
        embed = self._create_queue_embed(interaction)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_pending_sessions(self, guild_id: int):
        """Load pending onboarding sessions."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.guild_id == guild_id,
                        OnboardingSession.state == 'completed'
                    )
                )
                .order_by(OnboardingSession.completed_at.asc())
            )
            self.pending_sessions = result.scalars().all()

    def _create_queue_embed(self, interaction: discord.Interaction):
        """Create queue display embed."""
        embed = discord.Embed(
            title="📋 Onboarding Queue",
            description=f"Managing onboarding applications for {interaction.guild.name}",
            color=discord.Color.blue()
        )

        if not self.pending_sessions:
            embed.add_field(
                name="No Pending Applications",
                value="All onboarding applications have been processed.",
                inline=False
            )
            return embed

        # Show pending sessions (5 per page)
        start_idx = self.current_page * 5
        end_idx = min(start_idx + 5, len(self.pending_sessions))

        for i in range(start_idx, end_idx):
            session = self.pending_sessions[i]
            member = interaction.guild.get_member(session.user_id)
            member_name = member.display_name if member else f"Unknown ({session.user_id})"

            answer_count = len(session.answers) if session.answers else 0
            suggested_roles = session.suggestion.get('roles', []) if session.suggestion else []

            embed.add_field(
                name=f"{i+1}. {member_name}",
                value=(
                    f"**Completed:** {discord.utils.format_dt(session.completed_at, 'R')}\n"
                    f"**Answers:** {answer_count} response(s)\n"
                    f"**Suggested Roles:** {len(suggested_roles)}"
                ),
                inline=True
            )

        embed.set_footer(
            text=f"Page {self.current_page + 1}/{(len(self.pending_sessions) - 1) // 5 + 1} • {len(self.pending_sessions)} pending"
        )

        return embed

    @discord.ui.button(label="Review Applications", style=discord.ButtonStyle.primary, emoji="👀") # type: ignore[arg-type]
    async def review_applications(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Review individual applications."""
        if not self.pending_sessions:
            await interaction.response.send_message("No applications to review.", ephemeral=True)
            return

        # Show first application for review
        session = self.pending_sessions[0]
        view = ApplicationReviewView(session)
        await view.show_application(interaction)

    @discord.ui.button(label="Refresh Queue", style=discord.ButtonStyle.secondary, emoji="🔄") # type: ignore[arg-type]
    async def refresh_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the queue."""
        await self.load_pending_sessions(interaction.guild_id)
        self.current_page = 0
        embed = self._create_queue_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)


class ApplicationReviewView(discord.ui.View):
    """View for reviewing individual onboarding applications."""

    def __init__(self, session: OnboardingSession):
        super().__init__(timeout=300)
        self.session = session

    async def show_application(self, interaction: discord.Interaction):
        """Show application details."""
        member = interaction.guild.get_member(self.session.user_id)
        member_name = member.display_name if member else f"Unknown ({self.session.user_id})"

        embed = discord.Embed(
            title=f"📋 Application Review - {member_name}",
            description="Review this member's onboarding responses",
            color=discord.Color.blue()
        )

        # Show member info
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="Member Info",
                value=(
                    f"**Username:** {member.mention}\n"
                    f"**Joined:** {discord.utils.format_dt(member.joined_at, 'R')}\n"
                    f"**Account Created:** {discord.utils.format_dt(member.created_at, 'R')}"
                ),
                inline=False
            )

        # Show application info
        embed.add_field(
            name="Application Info",
            value=(
                f"**Completed:** {discord.utils.format_dt(self.session.completed_at, 'R')}\n"
                f"**Timezone:** {self.session.user_timezone or 'Not provided'}\n"
                f"**Answers:** {len(self.session.answers)} response(s)"
            ),
            inline=True
        )

        # Show suggested roles
        if self.session.suggestion and self.session.suggestion.get('roles'):
            role_names = []
            for role_id in self.session.suggestion['roles']:
                role = interaction.guild.get_role(role_id)
                role_names.append(role.mention if role else f"Unknown Role ({role_id})")

            embed.add_field(
                name="Suggested Roles",
                value="\n".join(role_names[:10]),
                inline=True
            )

        # Show answers
        if self.session.answers:
            answer_text = []
            for qid, answer in list(self.session.answers.items())[:5]:  # Show first 5 answers
                answer_display = str(answer)[:100] + ("..." if len(str(answer)) > 100 else "")
                answer_text.append(f"**{qid}:** {answer_display}")

            embed.add_field(
                name="Responses (First 5)",
                value="\n".join(answer_text),
                inline=False
            )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅") # type: ignore[arg-type]
    async def approve_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Approve the application."""
        try:
            # Update session status
            async with get_session() as session:
                await session.execute(
                    update(OnboardingSession)
                    .where(OnboardingSession.id == self.session.id)
                    .values(
                        state='approved',
                        reviewed_at=datetime.now(timezone.utc),
                        reviewed_by=interaction.user.id
                    )
                )
                await session.commit()

            embed = discord.Embed(
                title="✅ Application Approved",
                description="The member's application has been approved.",
                color=discord.Color.green()
            )

            # Apply suggested roles if any
            if self.session.suggestion and self.session.suggestion.get('roles'):
                member = interaction.guild.get_member(self.session.user_id)
                if member:
                    roles_to_add = []
                    for role_id in self.session.suggestion['roles']:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            roles_to_add.append(role)

                    if roles_to_add:
                        try:
                            await member.add_roles(*roles_to_add, reason=f"Onboarding approved by {interaction.user}")
                            embed.add_field(
                                name="Roles Assigned",
                                value="\n".join(role.mention for role in roles_to_add),
                                inline=False
                            )
                        except (discord.Forbidden, discord.HTTPException) as e:
                            embed.add_field(
                                name="⚠️ Role Assignment Failed",
                                value=f"Could not assign roles: {str(e)}",
                                inline=False
                            )

            await interaction.response.edit_message(embed=embed, view=None)

        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to approve application: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="❌") # type: ignore[arg-type]
    async def deny_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deny the application."""
        modal = DenyReasonModal(self.session)
        await interaction.response.send_modal(modal)


class DenyReasonModal(discord.ui.Modal):
    """Modal for entering denial reason."""

    def __init__(self, session: OnboardingSession):
        super().__init__(title="Deny Application")
        self.session = session

        self.reason_input = discord.ui.TextInput(
            label="Reason for Denial",
            placeholder="Enter the reason for denying this application...",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle denial submission."""
        try:
            reason = self.reason_input.value.strip()

            # Update session status
            async with get_session() as session:
                await session.execute(
                    update(OnboardingSession)
                    .where(OnboardingSession.id == self.session.id)
                    .values(
                        state='denied',
                        denial_reason=reason,
                        reviewed_at=datetime.now(timezone.utc),
                        reviewed_by=interaction.user.id
                    )
                )
                await session.commit()

            embed = discord.Embed(
                title="❌ Application Denied",
                description="The member's application has been denied.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )

            await interaction.response.edit_message(embed=embed, view=None)

        except (discord.HTTPException, discord.DiscordException) as e:
            # FIXED: Handle Discord-specific errors
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to deny application: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)