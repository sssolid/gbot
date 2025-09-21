"""
Onboarding views and modals for the Guild Management Bot
"""
import discord
from sqlalchemy import select, and_
from typing import Dict, List, Any, Optional
from datetime import datetime

from database import OnboardingQuestion, OnboardingSession, OnboardingRule, get_session
from utils.permissions import PermissionChecker


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
    """Multi-step onboarding wizard."""
    
    def __init__(self, session_id: Optional[int] = None):
        super().__init__(timeout=600)
        self.session_id = session_id
        self.current_question = 0
        self.questions: List[OnboardingQuestion] = []
        self.answers: Dict[str, Any] = {}
    
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
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.user_id == user_id,
                        OnboardingSession.guild_id == guild_id,
                        OnboardingSession.state == 'in_progress'
                    )
                )
            )
            existing_session = result.scalar_one_or_none()
            
            if existing_session:
                self.session_id = existing_session.id
                self.answers = existing_session.answers or {}
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
                    user_id=user_id,
                    guild_id=guild_id,
                    state='in_progress',
                    answers={}
                )
                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)
                self.session_id = new_session.id
    
    async def save_answer(self, qid: str, answer: Any):
        """Save an answer to the session."""
        self.answers[qid] = answer
        
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.answers = self.answers
            await session.commit()
    
    async def show_current_question(self, interaction: discord.Interaction):
        """Show the current question to the user."""
        if self.current_question >= len(self.questions):
            await self.complete_onboarding(interaction)
            return
        
        question = self.questions[self.current_question]
        
        embed = discord.Embed(
            title="📝 Onboarding Process",
            description=f"**Question {self.current_question + 1} of {len(self.questions)}**\n\n{question.prompt}",
            color=discord.Color.blue()
        )
        
        if question.required:
            embed.add_field(name="Required", value="This question is required", inline=False)
        
        view = None
        
        if question.type == 'single_select':
            view = SingleSelectView(self, question)
        elif question.type == 'text':
            view = TextInputView(self, question)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.edit_original_response(embed=embed, view=view)
    
    async def next_question(self, interaction: discord.Interaction):
        """Move to the next question."""
        self.current_question += 1
        await self.show_current_question(interaction)
    
    async def complete_onboarding(self, interaction: discord.Interaction):
        """Complete the onboarding process."""
        # Calculate role suggestions
        suggestions = await self.calculate_role_suggestions(interaction.guild_id)
        
        # Update session
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'completed'
            onboarding_session.completed_at = datetime.utcnow()
            onboarding_session.suggestion = suggestions
            await session.commit()
        
        # Send completion message
        embed = discord.Embed(
            title="✅ Onboarding Complete!",
            description=(
                "Thank you for completing the onboarding process! "
                "Your application has been submitted for review by our administrators.\n\n"
                "You will be notified once your application has been processed."
            ),
            color=discord.Color.green()
        )
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.edit_original_response(embed=embed, view=None)
        
        # Notify admins in onboarding queue
        await self.notify_admins(interaction)
    
    async def calculate_role_suggestions(self, guild_id: int) -> List[int]:
        """Calculate role suggestions based on answers and rules."""
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
        
        suggested_roles = set()
        
        for rule in rules:
            conditions = rule.when_conditions
            if self.matches_conditions(conditions):
                suggested_roles.update(rule.suggest_roles)
        
        return list(suggested_roles)
    
    def matches_conditions(self, conditions: List[Dict[str, str]]) -> bool:
        """Check if answers match rule conditions."""
        for condition in conditions:
            key = condition.get('key')
            expected_value = condition.get('value')
            
            actual_value = self.answers.get(key)
            if actual_value != expected_value:
                return False
        
        return True
    
    async def notify_admins(self, interaction: discord.Interaction):
        """Notify admins of new onboarding completion."""
        bot = interaction.client
        
        # Get guild config to find logs channel
        guild_config = await bot.get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config.logs_channel_id:
            return  # No logs channel configured
        
        logs_channel = bot.get_channel(guild_config.logs_channel_id)
        if not logs_channel:
            return  # Logs channel not found
        
        # Get the onboarding session details
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one_or_none()
            
            if not onboarding_session:
                return
        
        # Create notification embed
        embed = discord.Embed(
            title="📋 New Onboarding Completion",
            description=f"{interaction.user.mention} has completed the onboarding process and is awaiting review.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="User",
            value=f"{interaction.user.display_name} ({interaction.user.mention})",
            inline=True
        )
        
        embed.add_field(
            name="Completed",
            value=discord.utils.format_dt(onboarding_session.completed_at, 'R'),
            inline=True
        )
        
        # Show answers summary
        if onboarding_session.answers:
            answers_preview = []
            for qid, answer in list(onboarding_session.answers.items())[:3]:
                answers_preview.append(f"**{qid}**: {str(answer)[:80]}{'...' if len(str(answer)) > 80 else ''}")
            
            if answers_preview:
                embed.add_field(
                    name="Answers Preview",
                    value="\n".join(answers_preview),
                    inline=False
                )
                
                if len(onboarding_session.answers) > 3:
                    embed.add_field(
                        name="Additional Answers",
                        value=f"...and {len(onboarding_session.answers) - 3} more",
                        inline=False
                    )
        
        # Show role suggestions if any
        if onboarding_session.suggestion:
            role_suggestions = []
            for role_id in onboarding_session.suggestion[:5]:  # Show first 5
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_suggestions.append(role.mention)
                    else:
                        role_suggestions.append(f"Role ID: {role_id}")
                except (ValueError, TypeError):
                    # Handle string role names
                    role_suggestions.append(str(role_id))
            
            if role_suggestions:
                embed.add_field(
                    name="Suggested Roles",
                    value="\n".join(role_suggestions),
                    inline=False
                )
        
        embed.add_field(
            name="Review Action Required",
            value="Use the **Admin Dashboard → Onboarding Queue** to review and approve/deny this application.",
            inline=False
        )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Session ID: {onboarding_session.id}")
        
        try:
            # Create view with quick action buttons
            view = QuickOnboardingActionView(onboarding_session.id, interaction.user)
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


class SingleSelectView(discord.ui.View):
    """View for single select questions."""
    
    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question
        
        # Create select menu with options
        options = []
        for option in question.options or []:
            options.append(discord.SelectOption(
                label=option,
                value=option
            ))
        
        if options:
            select = discord.ui.Select(
                placeholder=f"Select your answer for: {question.prompt[:50]}...",
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


class TextInputView(discord.ui.View):
    """View for text input questions."""
    
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
    """Modal for text input questions."""
    
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


class OnboardingQueueView(discord.ui.View):
    """Admin view for the onboarding queue."""
    
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
        """Show the current queue page."""
        await self.load_sessions(interaction.guild_id)
        
        if not self.sessions:
            embed = discord.Embed(
                title="📋 Onboarding Queue",
                description="No pending applications at this time.",
                color=discord.Color.blue()
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Pagination
        per_page = 5
        start_idx = self.current_page * per_page
        end_idx = start_idx + per_page
        page_sessions = self.sessions[start_idx:end_idx]
        
        embed = discord.Embed(
            title="📋 Onboarding Queue",
            description=f"Page {self.current_page + 1} of {(len(self.sessions) - 1) // per_page + 1}",
            color=discord.Color.blue()
        )
        
        for session in page_sessions:
            user = interaction.guild.get_member(session.user_id)
            user_name = user.display_name if user else f"User {session.user_id}"
            
            answers_preview = []
            for qid, answer in (session.answers or {}).items():
                if len(answers_preview) < 3:  # Show first 3 answers
                    answers_preview.append(f"**{qid}**: {str(answer)[:50]}...")
            
            suggested_roles = session.suggestion or []
            roles_text = f"{len(suggested_roles)} roles suggested" if suggested_roles else "No roles suggested"
            
            embed.add_field(
                name=f"👤 {user_name}",
                value=(
                    f"**Completed**: {discord.utils.format_dt(session.completed_at, 'R')}\n"
                    f"**Roles**: {roles_text}\n"
                    f"**Answers**: {chr(10).join(answers_preview) if answers_preview else 'No answers'}"
                ),
                inline=False
            )
        
        # Update buttons
        self.update_buttons()
        
        await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update navigation buttons."""
        self.clear_items()
        
        # Navigation buttons
        if self.current_page > 0:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if (self.current_page + 1) * 5 < len(self.sessions):
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Action buttons for current page
        per_page = 5
        start_idx = self.current_page * per_page
        end_idx = start_idx + per_page
        page_sessions = self.sessions[start_idx:end_idx]
        
        for i, session in enumerate(page_sessions):
            approve_button = discord.ui.Button(
                label=f"✅ Approve #{start_idx + i + 1}",
                style=discord.ButtonStyle.success,
                custom_id=f"approve_{session.id}"
            )
            approve_button.callback = lambda inter, sess_id=session.id: self.approve_application(inter, sess_id)
            self.add_item(approve_button)
            
            deny_button = discord.ui.Button(
                label=f"❌ Deny #{start_idx + i + 1}",
                style=discord.ButtonStyle.danger,
                custom_id=f"deny_{session.id}"
            )
            deny_button.callback = lambda inter, sess_id=session.id: self.deny_application(inter, sess_id)
            self.add_item(deny_button)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_queue(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.sessions) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_queue(interaction)
    
    async def approve_application(self, interaction: discord.Interaction, session_id: int):
        """Approve an onboarding application."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "approve applications",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = ApprovalView(session_id)
        await interaction.response.send_message(
            "Review and approve application:",
            view=view,
            ephemeral=True
        )
    
    async def deny_application(self, interaction: discord.Interaction, session_id: int):
        """Deny an onboarding application."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "deny applications", 
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        modal = DenyModal(session_id)
        await interaction.response.send_modal(modal)


class ApprovalView(discord.ui.View):
    """View for approving applications with role selection."""
    
    def __init__(self, session_id: int):
        super().__init__(timeout=300)
        self.session_id = session_id
    
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles to assign...",
        max_values=10
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        """Select roles to assign."""
        self.selected_roles = select.values
        
        # Show confirmation
        role_mentions = [role.mention for role in select.values]
        embed = discord.Embed(
            title="✅ Confirm Approval",
            description=f"Assign the following roles:\n{chr(10).join(role_mentions)}",
            color=discord.Color.green()
        )
        
        confirm_view = ConfirmApprovalView(self.session_id, select.values)
        await interaction.response.edit_message(embed=embed, view=confirm_view)


class ConfirmApprovalView(discord.ui.View):
    """Confirmation view for approval."""
    
    def __init__(self, session_id: int, roles: List[discord.Role]):
        super().__init__(timeout=300)
        self.session_id = session_id
        self.roles = roles
    
    @discord.ui.button(label="Confirm Approval", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the approval."""
        # Update session status
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'approved'
            onboarding_session.reviewed_at = datetime.utcnow()
            onboarding_session.reviewed_by = interaction.user.id
            await session.commit()
        
        # Assign roles
        member = interaction.guild.get_member(onboarding_session.user_id)
        if member:
            try:
                await member.add_roles(*self.roles, reason="Onboarding approval")
                
                # Send success message
                embed = discord.Embed(
                    title="✅ Application Approved",
                    description=f"Successfully approved {member.mention} and assigned {len(self.roles)} role(s).",
                    color=discord.Color.green()
                )
                
                # Log the action
                bot = interaction.client
                await bot.log_action(
                    interaction.guild_id,
                    "Onboarding Approval",
                    interaction.user,
                    member,
                    f"Assigned roles: {', '.join(role.name for role in self.roles)}"
                )
                
            except discord.Forbidden:
                embed = PermissionChecker.get_bot_permission_error_embed(
                    "assign roles",
                    "Manage Roles (with proper role hierarchy)"
                )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to assign roles: {str(e)}",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Member not found in guild.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=None)


class DenyModal(discord.ui.Modal):
    """Modal for denying applications with reason."""
    
    def __init__(self, session_id: int):
        super().__init__(title="Deny Application")
        self.session_id = session_id
        
        self.reason_input = discord.ui.TextInput(
            label="Reason for denial",
            placeholder="Enter the reason for denying this application...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle denial submission."""
        reason = self.reason_input.value
        
        # Update session status
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
            )
            onboarding_session = result.scalar_one()
            onboarding_session.state = 'denied'
            onboarding_session.reviewed_at = datetime.utcnow()
            onboarding_session.reviewed_by = interaction.user.id
            onboarding_session.denial_reason = reason
            await session.commit()
        
        # Send notification to user (optional)
        member = interaction.guild.get_member(onboarding_session.user_id)
        if member:
            try:
                dm_embed = discord.Embed(
                    title=f"Onboarding Application - {interaction.guild.name}",
                    description=f"Your application has been reviewed.\n\n**Status**: Denied\n**Reason**: {reason}",
                    color=discord.Color.red()
                )
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled
        
        # Send confirmation
        embed = discord.Embed(
            title="❌ Application Denied",
            description=f"Application denied. Reason: {reason}",
            color=discord.Color.red()
        )
        
        # Log the action
        bot = interaction.client
        await bot.log_action(
            interaction.guild_id,
            "Onboarding Denial",
            interaction.user,
            member,
            f"Reason: {reason}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuickOnboardingActionView(discord.ui.View):
    """Quick action buttons for onboarding notifications."""
    def __init__(self, session_id: int):
        super().__init__(timeout=None)  # persistent view
        self._add_review_button(session_id)

    def _add_review_button(self, session_id: int):
        btn = discord.ui.Button(
            label="Review Application",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            custom_id=f"onboarding_review_{session_id}",
        )
        btn.callback = self.review_application  # bind callback
        self.add_item(btn)

    async def review_application(self, interaction: discord.Interaction):
        # derive the session id from the custom_id (don’t rely on self.* for persistent views)
        cid = interaction.data["custom_id"]
        session_id = int(cid.removeprefix("onboarding_review_"))

        from utils.permissions import PermissionChecker
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "review onboarding applications",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # DB lookup
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == session_id)
            )
            onboarding_session = result.scalar_one_or_none()

        if not onboarding_session:
            embed = discord.Embed(
                title="❌ Session Not Found",
                description="This onboarding session no longer exists.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if onboarding_session.state != "completed":
            embed = discord.Embed(
                title="ℹ️ Already Processed",
                description=f"This application has already been {onboarding_session.state}.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Use interaction.user rather than storing user on the view
        view = DetailedOnboardingReviewView(onboarding_session, interaction.user)
        await view.show_review(interaction)


class DetailedOnboardingReviewView(discord.ui.View):
    """Detailed review interface for a specific onboarding session."""
    
    def __init__(self, session: OnboardingSession, user: discord.Member):
        super().__init__(timeout=300)
        self.session = session
        self.user = user
    
    async def show_review(self, interaction: discord.Interaction):
        """Show detailed review interface."""
        embed = discord.Embed(
            title=f"📋 Onboarding Review - {self.user.display_name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="User Information",
            value=(
                f"**Display Name:** {self.user.display_name}\n"
                f"**Username:** {self.user.name}\n"
                f"**User ID:** {self.user.id}\n"
                f"**Account Created:** {discord.utils.format_dt(self.user.created_at, 'R')}\n"
                f"**Joined Server:** {discord.utils.format_dt(self.user.joined_at, 'R') if self.user.joined_at else 'Unknown'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Application Details",
            value=(
                f"**Started:** {discord.utils.format_dt(self.session.created_at, 'R')}\n"
                f"**Completed:** {discord.utils.format_dt(self.session.completed_at, 'R')}\n"
                f"**Session ID:** {self.session.id}"
            ),
            inline=False
        )
        
        # Show all answers
        if self.session.answers:
            answers_text = []
            for qid, answer in self.session.answers.items():
                answers_text.append(f"**{qid}:** {str(answer)}")
            
            # Split into multiple fields if too long
            answers_str = "\n".join(answers_text)
            if len(answers_str) <= 1024:
                embed.add_field(
                    name="Answers",
                    value=answers_str,
                    inline=False
                )
            else:
                # Split into chunks
                chunks = []
                current_chunk = []
                current_length = 0
                
                for answer_line in answers_text:
                    if current_length + len(answer_line) + 1 > 1024:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [answer_line]
                        current_length = len(answer_line)
                    else:
                        current_chunk.append(answer_line)
                        current_length += len(answer_line) + 1
                
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                
                for i, chunk in enumerate(chunks[:3]):  # Max 3 fields
                    field_name = "Answers" if i == 0 else f"Answers (cont. {i+1})"
                    embed.add_field(name=field_name, value=chunk, inline=False)
        
        # Show role suggestions
        if self.session.suggestion:
            role_suggestions = []
            for role_id in self.session.suggestion:
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_suggestions.append(role.mention)
                    else:
                        role_suggestions.append(f"Role ID: {role_id} (not found)")
                except (ValueError, TypeError):
                    role_suggestions.append(str(role_id))
            
            embed.add_field(
                name="Suggested Roles",
                value="\n".join(role_suggestions) if role_suggestions else "None",
                inline=False
            )
        
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        self.update_buttons()
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    def update_buttons(self):
        """Update action buttons."""
        self.clear_items()
        
        # Approve button
        approve_button = discord.ui.Button(
            label="Approve Application",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        approve_button.callback = self.approve_application
        self.add_item(approve_button)
        
        # Deny button
        deny_button = discord.ui.Button(
            label="Deny Application",
            style=discord.ButtonStyle.danger,
            emoji="❌"
        )
        deny_button.callback = self.deny_application
        self.add_item(deny_button)
        
        # Custom roles button
        custom_roles_button = discord.ui.Button(
            label="Custom Role Assignment",
            style=discord.ButtonStyle.secondary,
            emoji="🎭"
        )
        custom_roles_button.callback = self.custom_role_assignment
        self.add_item(custom_roles_button)
    
    async def approve_application(self, interaction: discord.Interaction):
        """Approve the application with suggested roles."""
        # Get suggested roles
        suggested_role_objects = []
        if self.session.suggestion:
            for role_id in self.session.suggestion:
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        suggested_role_objects.append(role)
                except (ValueError, TypeError):
                    pass  # Skip invalid role IDs
        
        if suggested_role_objects:
            view = ApprovalView(self.session.id, suggested_role_objects)
            
            embed = discord.Embed(
                title="✅ Confirm Approval",
                description=f"Approve {self.user.mention} and assign the following suggested roles:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Roles to Assign",
                value="\n".join(role.mention for role in suggested_role_objects),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # No suggested roles, approve without roles
            view = ConfirmApprovalView(self.session.id, [])
            
            embed = discord.Embed(
                title="✅ Confirm Approval",
                description=f"Approve {self.user.mention} with no additional roles?",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def deny_application(self, interaction: discord.Interaction):
        """Deny the application."""
        modal = DenyModal(self.session.id)
        await interaction.response.send_modal(modal)
    
    async def custom_role_assignment(self, interaction: discord.Interaction):
        """Custom role assignment interface."""
        view = CustomRoleApprovalView(self.session.id)
        
        embed = discord.Embed(
            title="🎭 Custom Role Assignment",
            description=f"Select custom roles to assign to {self.user.mention}:",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CustomRoleApprovalView(discord.ui.View):
    """Custom role selection for approval."""
    
    def __init__(self, session_id: int):
        super().__init__(timeout=300)
        self.session_id = session_id
    
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles to assign...",
        max_values=10
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        """Select custom roles."""
        selected_roles = select.values
        
        view = ConfirmApprovalView(self.session_id, selected_roles)
        
        embed = discord.Embed(
            title="✅ Confirm Custom Approval",
            description="Approve application and assign the selected roles:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Roles to Assign",
            value="\n".join(role.mention for role in selected_roles) if selected_roles else "No roles",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)