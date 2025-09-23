"""
Enhanced onboarding views and modals for the Guild Management Bot - FIXED VERSION
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import discord
from sqlalchemy import select, and_

from database import OnboardingQuestion, OnboardingSession, get_session, GuildConfig
from utils.constants import TIMEZONES, MO2_RACES, MO2_ARCHETYPES, MO2_PROFESSIONS


class WelcomeView(discord.ui.View):
    """Welcome view with onboarding button."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="Start Onboarding",
        style=discord.ButtonStyle.primary,
        emoji="🚀"
    )
    async def start_onboarding(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the onboarding process."""
        await interaction.response.send_message(
            "Starting onboarding process...",
            view=OnboardingWizard(),
            ephemeral=True
        )


class OnboardingWizard(discord.ui.View):
    """Enhanced multi-step onboarding wizard with timezone support."""

    def __init__(self, session_id: Optional[int] = None):
        super().__init__(timeout=600)
        self.session_id = session_id
        self.current_question = 0
        self.questions: List[OnboardingQuestion] = []
        self.answers: Dict[str, Any] = {}
        self.user_timezone: Optional[str] = None

    async def load_questions(self, guild_id: int):
        """Load active onboarding questions for the guild."""
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
            # Check for existing in-progress session
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.guild_id == guild_id,
                        OnboardingSession.user_id == user_id,
                        OnboardingSession.state == 'in_progress'
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
                    state='in_progress',
                    answers={},
                    created_at=datetime.now(timezone.utc)
                )
                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)

                self.session_id = new_session.id
                self.answers = {}
                self.current_question = 0

    async def save_answer(self, qid: str, answer: Any):
        """Save answer to database."""
        self.answers[qid] = answer

        # Special handling for timezone
        if qid == "timezone_required" or (hasattr(self, 'questions') and
                                         self.current_question < len(self.questions) and
                                         self.questions[self.current_question].type == "timezone"):
            self.user_timezone = answer

        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.answers = self.answers
            onboarding_session.user_timezone = self.user_timezone
            onboarding_session.updated_at = datetime.now(timezone.utc)
            await session.commit()

    async def show_current_question(self, interaction: discord.Interaction):
        """Show the current question to the user with enhanced UI."""
        if self.current_question >= len(self.questions):
            await self.complete_onboarding(interaction)
            return

        question = self.questions[self.current_question]

        embed = discord.Embed(
            title="📝 Guild Onboarding",
            description=f"**Question {self.current_question + 1} of {len(self.questions)}**\n\n{question.prompt}",
            color=discord.Color.blue()
        )

        if question.required:
            embed.add_field(name="Required", value="✅ This question is required", inline=False)

        # Add progress bar
        progress = self.current_question / len(self.questions)
        progress_bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))
        embed.add_field(name="Progress", value=f"`{progress_bar}` {int(progress * 100)}%", inline=False)

        view = None

        if question.type == 'single_select':
            view = SingleSelectView(self, question)
        elif question.type == 'multi_select':
            view = MultiSelectView(self, question)
        elif question.type == 'text':
            view = TextInputView(self, question)
        elif question.type == 'timezone':
            view = TimezoneSelectView(self, question)
        elif question.type == 'race':
            view = RaceSelectView(self, question)
        elif question.type == 'archetype':
            view = ArchetypeSelectView(self, question)
        elif question.type == 'profession':
            view = ProfessionSelectView(self, question)
        else:
            # Fallback to text input for unknown types
            view = TextInputView(self, question)

        embed.set_footer(text="💡 You can return to complete this later if needed")

        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)

    async def next_question(self, interaction: discord.Interaction):
        """Move to the next question."""
        self.current_question += 1
        await self.show_current_question(interaction)

    async def complete_onboarding(self, interaction: discord.Interaction):
        """Complete the onboarding process with enhanced completion."""
        # Calculate role suggestions (simplified for now)
        suggestions = await self.calculate_role_suggestions(interaction.guild_id)

        # Update session
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'completed'
            onboarding_session.completed_at = datetime.now(timezone.utc)
            onboarding_session.suggestion = suggestions
            await session.commit()

        # Send completion message
        embed = discord.Embed(
            title="✅ Onboarding Complete!",
            description=(
                "Thank you for completing the guild onboarding process! "
                "Your application has been submitted for review by our administrators.\n\n"
                "You will be notified once your application has been processed."
            ),
            color=discord.Color.green()
        )

        # Add summary of answers
        if self.answers:
            summary_text = []
            for question in self.questions:
                if question.qid in self.answers:
                    answer = self.answers[question.qid]
                    if isinstance(answer, list):
                        answer_text = ", ".join(answer)
                    else:
                        answer_text = str(answer)

                    summary_text.append(f"**{question.prompt[:50]}{'...' if len(question.prompt) > 50 else ''}**\n{answer_text}")

            if summary_text:
                embed.add_field(
                    name="Your Responses",
                    value="\n\n".join(summary_text[:5]),  # Show first 5 responses
                    inline=False
                )

        if self.user_timezone:
            embed.add_field(
                name="Timezone",
                value=f"🌍 {self.user_timezone}",
                inline=True
            )

        embed.set_footer(text="🎉 Welcome to the guild! An admin will review your application soon.")

        # Send to logs channel if configured
        await self.log_completion(interaction)

        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.edit_original_response(embed=embed, view=None)

    async def calculate_role_suggestions(self, guild_id: int) -> List[int]:
        """Calculate role suggestions based on answers (simplified)."""
        # This is a placeholder - implement rule-based suggestions later
        return []

    async def log_completion(self, interaction: discord.Interaction):
        """Log completion to admin logs channel."""
        async with get_session() as session:
            guild_config = await session.get(GuildConfig, interaction.guild_id)

            if not guild_config or not guild_config.logs_channel_id:
                return  # No logs channel configured

            logs_channel = interaction.guild.get_channel(guild_config.logs_channel_id)
            if not logs_channel:
                return

        embed = discord.Embed(
            title="📝 New Onboarding Completion",
            description=f"{interaction.user.mention} has completed the onboarding process",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="User",
            value=f"{interaction.user.mention}\n({interaction.user.id})",
            inline=True
        )

        if self.user_timezone:
            embed.add_field(
                name="Timezone",
                value=self.user_timezone,
                inline=True
            )

        embed.add_field(
            name="Questions Answered",
            value=str(len(self.answers)),
            inline=True
        )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Session ID: {self.session_id}")

        try:
            # Create view with quick action buttons
            view = QuickOnboardingActionView(self.session_id, interaction.user)
            await logs_channel.send(embed=embed, view=view)
        except Exception as e:
            # If we can't send with view, try without
            try:
                await logs_channel.send(embed=embed)
            except Exception:
                pass  # Silently fail if we can't send to logs

    @discord.ui.button(
        label="Start",
        style=discord.ButtonStyle.primary,
        emoji="▶️"
    )
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the onboarding process."""
        await self.load_questions(interaction.guild_id)
        await self.load_session(interaction.user.id, interaction.guild_id)

        if not self.questions:
            embed = discord.Embed(
                title="❌ No Questions Available",
                description="There are no onboarding questions configured for this server.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        await self.show_current_question(interaction)


# Enhanced question view components

class SingleSelectView(discord.ui.View):
    """Enhanced view for single select questions."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create select menu with options
        options = []
        for option in (question.options or []):
            options.append(discord.SelectOption(
                label=option[:100],  # Discord limit
                value=option,
                emoji="📝"
            ))

        if options:
            select = discord.ui.Select(
                placeholder=f"Select your answer...",
                options=options,
                custom_id=f"onboarding_select_{question.id}"
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle select option."""
        selected_value = interaction.data['values'][0]
        await self.wizard.save_answer(self.question.qid, selected_value)
        await self.wizard.next_question(interaction)


class MultiSelectView(discord.ui.View):
    """View for multi-select questions."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create select menu with options
        options = []
        for option in (question.options or []):
            options.append(discord.SelectOption(
                label=option[:100],  # Discord limit
                value=option,
                emoji="☑️"
            ))

        if options:
            select = discord.ui.Select(
                placeholder=f"Select multiple answers...",
                options=options,
                max_values=min(len(options), 25),  # Discord limits
                custom_id=f"onboarding_multiselect_{question.id}"
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle multi-select options."""
        selected_values = interaction.data['values']
        await self.wizard.save_answer(self.question.qid, selected_values)
        await self.wizard.next_question(interaction)


class TimezoneSelectView(discord.ui.View):
    """Enhanced timezone selection view."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create timezone options (split into multiple selects if needed)
        options = []
        for tz in TIMEZONES[:25]:  # Discord limit
            offset = tz.replace("UTC", "")
            description = f"UTC offset: {offset}"

            options.append(discord.SelectOption(
                label=tz,
                value=tz,
                description=description,
                emoji="🌍"
            ))

        select = discord.ui.Select(
            placeholder="Select your timezone...",
            options=options
        )
        select.callback = self.select_timezone
        self.add_item(select)

    async def select_timezone(self, interaction: discord.Interaction):
        """Handle timezone selection."""
        selected_timezone = interaction.data['values'][0]
        await self.wizard.save_answer(self.question.qid, selected_timezone)
        await self.wizard.next_question(interaction)


class RaceSelectView(discord.ui.View):
    """MO2 race selection view."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create race options
        options = []
        for race in MO2_RACES[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=race,
                value=race,
                emoji="🧬"
            ))

        select = discord.ui.Select(
            placeholder="Select your character race...",
            options=options
        )
        select.callback = self.select_race
        self.add_item(select)

    async def select_race(self, interaction: discord.Interaction):
        """Handle race selection."""
        selected_race = interaction.data['values'][0]
        await self.wizard.save_answer(self.question.qid, selected_race)
        await self.wizard.next_question(interaction)


class ArchetypeSelectView(discord.ui.View):
    """MO2 archetype selection view."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create archetype options
        options = []
        for archetype_name, archetype_data in MO2_ARCHETYPES.items():
            emoji = "⚔️" if archetype_name == "Warrior" else "🔮" if archetype_name == "Mage" else "🎯"
            options.append(discord.SelectOption(
                label=archetype_name,
                value=archetype_name,
                description=f"Various {archetype_name.lower()} builds",
                emoji=emoji
            ))

        select = discord.ui.Select(
            placeholder="Select your character archetype...",
            options=options
        )
        select.callback = self.select_archetype
        self.add_item(select)

    async def select_archetype(self, interaction: discord.Interaction):
        """Handle archetype selection."""
        selected_archetype = interaction.data['values'][0]
        await self.wizard.save_answer(self.question.qid, selected_archetype)
        await self.wizard.next_question(interaction)


class ProfessionSelectView(discord.ui.View):
    """MO2 profession selection view."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

        # Create profession options (limit to first 25)
        options = []
        for profession in MO2_PROFESSIONS[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=profession,
                value=profession,
                emoji="🛠️"
            ))

        select = discord.ui.Select(
            placeholder="Select your main professions/skills...",
            options=options,
            max_values=min(len(options), 10)  # Allow multiple selections
        )
        select.callback = self.select_professions
        self.add_item(select)

    async def select_professions(self, interaction: discord.Interaction):
        """Handle profession selection."""
        selected_professions = interaction.data['values']
        await self.wizard.save_answer(self.question.qid, selected_professions)
        await self.wizard.next_question(interaction)


class TextInputView(discord.ui.View):
    """Enhanced view for text input questions."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question

    @discord.ui.button(
        label="Answer",
        style=discord.ButtonStyle.primary,
        emoji="✏️"
    )
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open text input modal."""
        modal = TextInputModal(self.wizard, self.question)
        await interaction.response.send_modal(modal)


class TextInputModal(discord.ui.Modal):
    """Enhanced modal for text input questions."""

    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(title=f"Answer: {question.prompt[:50]}...")
        self.wizard = wizard
        self.question = question

        self.text_input = discord.ui.TextInput(
            label=question.prompt[:45],
            placeholder="Enter your answer here...",
            style=discord.TextStyle.paragraph if len(question.prompt) > 100 else discord.TextStyle.short,
            required=question.required,
            max_length=1000
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle text input submission."""
        answer = self.text_input.value
        await self.wizard.save_answer(self.question.qid, answer)
        await self.wizard.next_question(interaction)


# Admin views for managing onboarding queue

class OnboardingQueueView(discord.ui.View):
    """Enhanced admin view for the onboarding queue."""

    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.sessions: List[OnboardingSession] = []

    async def load_sessions(self, guild_id: int):
        """Load pending onboarding sessions."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.guild_id == guild_id,
                        OnboardingSession.state == 'completed'  # Only completed, not yet approved/denied
                    )
                )
                .order_by(OnboardingSession.completed_at.desc())
            )
            self.sessions = result.scalars().all()

    async def show_queue(self, interaction: discord.Interaction):
        """Show the current queue page with enhanced information."""
        await self.load_sessions(interaction.guild_id)

        if not self.sessions:
            embed = discord.Embed(
                title="📋 Onboarding Queue",
                description="No pending applications at this time.",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Queue Status",
                value="✅ All applications processed",
                inline=False
            )

            await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
            return

        # Pagination
        per_page = 5
        total_pages = (len(self.sessions) - 1) // per_page + 1
        start_idx = self.current_page * per_page
        end_idx = min(start_idx + per_page, len(self.sessions))

        embed = discord.Embed(
            title="📋 Onboarding Queue",
            description=f"**{len(self.sessions)} pending applications** (Page {self.current_page + 1}/{total_pages})",
            color=discord.Color.orange()
        )

        for session in self.sessions[start_idx:end_idx]:
            user = interaction.guild.get_member(session.user_id)
            if not user:
                continue

            completed_time = discord.utils.format_dt(session.completed_at, 'R')
            timezone_info = f" | 🌍 {session.user_timezone}" if session.user_timezone else ""

            embed.add_field(
                name=f"👤 {user.display_name}",
                value=f"Completed {completed_time}{timezone_info}\n**Answers:** {len(session.answers)} questions",
                inline=False
            )

        # Add navigation and action buttons
        self.clear_items()

        if total_pages > 1:
            if self.current_page > 0:
                prev_button = discord.ui.Button(label="Previous", emoji="⬅️", style=discord.ButtonStyle.secondary)
                prev_button.callback = self.previous_page
                self.add_item(prev_button)

            if self.current_page < total_pages - 1:
                next_button = discord.ui.Button(label="Next", emoji="➡️", style=discord.ButtonStyle.secondary)
                next_button.callback = self.next_page
                self.add_item(next_button)

        # Review button
        if self.sessions:
            review_button = discord.ui.Button(label="Review Applications", emoji="👁️", style=discord.ButtonStyle.primary)
            review_button.callback = self.review_applications
            self.add_item(review_button)

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_queue(interaction)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        self.current_page += 1
        await self.show_queue(interaction)

    async def review_applications(self, interaction: discord.Interaction):
        """Show application review interface."""
        view = ApplicationReviewView(self.sessions)
        await view.show_review_interface(interaction)


class ApplicationReviewView(discord.ui.View):
    """Enhanced view for reviewing individual applications."""

    def __init__(self, sessions: List[OnboardingSession]):
        super().__init__(timeout=600)
        self.sessions = sessions
        self.current_session_index = 0

    async def show_review_interface(self, interaction: discord.Interaction):
        """Show detailed review interface for applications."""
        if not self.sessions:
            await interaction.response.send_message("No applications to review.", ephemeral=True)
            return

        await self.show_current_application(interaction)

    async def show_current_application(self, interaction: discord.Interaction):
        """Show current application details."""
        if self.current_session_index >= len(self.sessions):
            embed = discord.Embed(
                title="✅ All Applications Reviewed",
                description="You have reviewed all pending applications.",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return

        session = self.sessions[self.current_session_index]
        user = interaction.guild.get_member(session.user_id)

        if not user:
            # Skip deleted users
            self.current_session_index += 1
            await self.show_current_application(interaction)
            return

        embed = discord.Embed(
            title=f"📝 Application Review ({self.current_session_index + 1}/{len(self.sessions)})",
            description=f"**Applicant:** {user.mention}\n**Completed:** {discord.utils.format_dt(session.completed_at, 'F')}",
            color=discord.Color.blue()
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        if session.user_timezone:
            embed.add_field(
                name="🌍 Timezone",
                value=session.user_timezone,
                inline=True
            )

        embed.add_field(
            name="📊 Progress",
            value=f"{len(session.answers)} questions answered",
            inline=True
        )

        # Show answers
        if session.answers:
            # Load questions to get prompts
            async with get_session() as db_session:
                result = await db_session.execute(
                    select(OnboardingQuestion)
                    .where(OnboardingQuestion.guild_id == interaction.guild_id)
                )
                questions = {q.qid: q for q in result.scalars().all()}

            answer_text = []
            for qid, answer in session.answers.items():
                question = questions.get(qid)
                if question:
                    if isinstance(answer, list):
                        answer_display = ", ".join(answer)
                    else:
                        answer_display = str(answer)

                    answer_text.append(f"**{question.prompt[:50]}{'...' if len(question.prompt) > 50 else ''}**\n{answer_display}")

            if answer_text:
                # Split answers into multiple fields if too long
                for i in range(0, len(answer_text), 3):
                    field_answers = answer_text[i:i+3]
                    embed.add_field(
                        name=f"Responses ({i+1}-{min(i+3, len(answer_text))})",
                        value="\n\n".join(field_answers),
                        inline=False
                    )

        # Update view with action buttons
        self.clear_items()

        # Navigation
        if len(self.sessions) > 1:
            if self.current_session_index > 0:
                prev_button = discord.ui.Button(label="Previous", emoji="⬅️", style=discord.ButtonStyle.secondary)
                prev_button.callback = self.previous_application
                self.add_item(prev_button)

            if self.current_session_index < len(self.sessions) - 1:
                next_button = discord.ui.Button(label="Next", emoji="➡️", style=discord.ButtonStyle.secondary)
                next_button.callback = self.next_application
                self.add_item(next_button)

        # Action buttons
        approve_button = discord.ui.Button(label="Approve", emoji="✅", style=discord.ButtonStyle.success)
        approve_button.callback = self.approve_application
        self.add_item(approve_button)

        deny_button = discord.ui.Button(label="Deny", emoji="❌", style=discord.ButtonStyle.danger)
        deny_button.callback = self.deny_application
        self.add_item(deny_button)

        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    async def previous_application(self, interaction: discord.Interaction):
        """Go to previous application."""
        self.current_session_index = max(0, self.current_session_index - 1)
        await self.show_current_application(interaction)

    async def next_application(self, interaction: discord.Interaction):
        """Go to next application."""
        self.current_session_index += 1
        await self.show_current_application(interaction)

    async def approve_application(self, interaction: discord.Interaction):
        """Approve the current application."""
        session = self.sessions[self.current_session_index]
        user = interaction.guild.get_member(session.user_id)

        if not user:
            await interaction.response.send_message("User no longer in server.", ephemeral=True)
            return

        view = ApprovalRoleSelectionView(session, user, self)

        embed = discord.Embed(
            title="✅ Approve Application",
            description=f"Select roles to assign to {user.mention}:",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def deny_application(self, interaction: discord.Interaction):
        """Deny the current application."""
        session = self.sessions[self.current_session_index]
        user = interaction.guild.get_member(session.user_id)

        if not user:
            await interaction.response.send_message("User no longer in server.", ephemeral=True)
            return

        modal = DenyApplicationModal(session, user, self)
        await interaction.response.send_modal(modal)


class ApprovalRoleSelectionView(discord.ui.View):
    """Enhanced role selection for approval."""

    def __init__(self, session: OnboardingSession, user: discord.Member, parent_view: ApplicationReviewView):
        super().__init__(timeout=300)
        self.session = session
        self.user = user
        self.parent_view = parent_view

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles to assign...",
        max_values=10
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        """Handle role selection for approval."""
        roles = select.values

        # Confirm approval
        view = ConfirmApprovalView(self.session, self.user, roles, self.parent_view)

        embed = discord.Embed(
            title="✅ Confirm Approval",
            description=f"Approve {self.user.mention} and assign the following roles:",
            color=discord.Color.green()
        )

        if roles:
            embed.add_field(
                name="Roles to Assign",
                value="\n".join(role.mention for role in roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Roles to Assign",
                value="No additional roles",
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmApprovalView(discord.ui.View):
    """Enhanced confirmation view for approval."""

    def __init__(self, session: OnboardingSession, user: discord.Member, roles: List[discord.Role], parent_view: ApplicationReviewView):
        super().__init__(timeout=300)
        self.session = session
        self.user = user
        self.roles = roles
        self.parent_view = parent_view

    @discord.ui.button(label="Confirm Approval", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_approval(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Execute the approval with enhanced feedback."""
        # Update session status
        async with get_session() as db_session:
            result = await db_session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session.id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'approved'
            onboarding_session.reviewed_at = datetime.now(timezone.utc)
            onboarding_session.reviewed_by = interaction.user.id
            await db_session.commit()

        # Assign roles
        success_roles = []
        failed_roles = []

        for role in self.roles:
            try:
                await self.user.add_roles(role, reason=f"Onboarding approval by {interaction.user}")
                success_roles.append(role)
            except Exception:
                failed_roles.append(role)

        # Add default member role if configured
        async with get_session() as db_session:
            guild_config = await db_session.get(GuildConfig, interaction.guild_id)
            if guild_config and guild_config.default_member_role_id:
                default_role = interaction.guild.get_role(guild_config.default_member_role_id)
                if default_role and default_role not in self.user.roles:
                    try:
                        await self.user.add_roles(default_role, reason=f"Default member role - approved by {interaction.user}")
                        success_roles.append(default_role)
                    except Exception:
                        failed_roles.append(default_role)

        # Send approval notification to user
        try:
            dm_embed = discord.Embed(
                title="🎉 Application Approved!",
                description=f"Your application to **{interaction.guild.name}** has been approved!",
                color=discord.Color.green()
            )

            if success_roles:
                dm_embed.add_field(
                    name="Roles Assigned",
                    value="\n".join(role.name for role in success_roles),
                    inline=False
                )

            dm_embed.add_field(
                name="Welcome!",
                value="You now have full access to the server. Welcome to the guild!",
                inline=False
            )

            await self.user.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled

        # Create response embed
        embed = discord.Embed(
            title="✅ Application Approved",
            description=f"Successfully approved {self.user.mention}",
            color=discord.Color.green()
        )

        if success_roles:
            embed.add_field(
                name="Roles Assigned",
                value="\n".join(role.mention for role in success_roles),
                inline=False
            )

        if failed_roles:
            embed.add_field(
                name="Failed to Assign",
                value="\n".join(role.mention for role in failed_roles),
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=None)

        # Remove from parent view's session list and continue
        self.parent_view.sessions.remove(self.session)
        if self.parent_view.current_session_index >= len(self.parent_view.sessions):
            self.parent_view.current_session_index = max(0, len(self.parent_view.sessions) - 1)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_approval(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the approval."""
        embed = discord.Embed(
            title="❌ Approval Cancelled",
            description="Application approval cancelled.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class DenyApplicationModal(discord.ui.Modal):
    """Enhanced modal for denying applications with reason."""

    def __init__(self, session: OnboardingSession, user: discord.Member, parent_view: ApplicationReviewView):
        super().__init__(title="Deny Application")
        self.session = session
        self.user = user
        self.parent_view = parent_view

        self.reason_input = discord.ui.TextInput(
            label="Denial Reason",
            placeholder="Provide a reason for denial (will be sent to the user)...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle application denial with enhanced feedback."""
        reason = self.reason_input.value.strip()

        # Update session status
        async with get_session() as db_session:
            result = await db_session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session.id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'denied'
            onboarding_session.reviewed_at = datetime.now(timezone.utc)
            onboarding_session.reviewed_by = interaction.user.id
            onboarding_session.denial_reason = reason
            await db_session.commit()

        # Send denial notification to user
        try:
            dm_embed = discord.Embed(
                title="❌ Application Denied",
                description=f"Your application to **{interaction.guild.name}** has been denied.",
                color=discord.Color.red()
            )

            dm_embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )

            dm_embed.add_field(
                name="What's Next?",
                value="You may be able to reapply in the future. Please contact an administrator if you have questions.",
                inline=False
            )

            await self.user.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled

        # Create response embed
        embed = discord.Embed(
            title="❌ Application Denied",
            description=f"Denied application from {self.user.mention}",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Remove from parent view's session list and continue
        self.parent_view.sessions.remove(self.session)
        if self.parent_view.current_session_index >= len(self.parent_view.sessions):
            self.parent_view.current_session_index = max(0, len(self.parent_view.sessions) - 1)


class QuickOnboardingActionView(discord.ui.View):
    """Quick action buttons for onboarding log entries."""

    def __init__(self, session_id: int, user: discord.Member):
        super().__init__(timeout=None)  # Persistent view
        self.session_id = session_id
        self.user = user

    @discord.ui.button(label="Quick Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def quick_approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quick approve with default roles."""
        async with get_session() as db_session:
            # Update session
            result = await db_session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            session = result.scalar_one_or_none()

            if not session or session.state != 'completed':
                await interaction.response.send_message("Application no longer pending.", ephemeral=True)
                return

            session.state = 'approved'
            session.reviewed_at = datetime.now(timezone.utc)
            session.reviewed_by = interaction.user.id

            # Add default member role if configured
            guild_config = await db_session.get(GuildConfig, interaction.guild_id)
            if guild_config and guild_config.default_member_role_id:
                default_role = interaction.guild.get_role(guild_config.default_member_role_id)
                if default_role:
                    try:
                        await self.user.add_roles(default_role, reason=f"Quick approval by {interaction.user}")
                    except Exception:
                        pass

            await db_session.commit()

        embed = discord.Embed(
            title="✅ Quick Approval",
            description=f"Quickly approved {self.user.mention}",
            color=discord.Color.green()
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Review", style=discord.ButtonStyle.primary, emoji="👁️")
    async def review_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open detailed review."""
        async with get_session() as db_session:
            result = await db_session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                await interaction.response.send_message("Application not found.", ephemeral=True)
                return

        view = ApplicationReviewView([session])
        await view.show_review_interface(interaction)