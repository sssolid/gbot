"""
Onboarding views and modals for the Guild Management Bot - FIXED VERSION
"""
import discord
from sqlalchemy import select, and_, update
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
        wizard = OnboardingWizard()
        await wizard.load_questions(interaction.guild_id)
        await wizard.load_session(interaction.user.id, interaction.guild_id)
        await wizard.show_current_question(interaction)


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
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
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
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Show suggested roles if any
        if suggestions:
            role_mentions = []
            for role_id in suggestions[:5]:  # Show first 5
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_mentions.append(role.mention)
                    else:
                        role_mentions.append(f"Role ID: {role_id}")
                except (ValueError, TypeError):
                    role_mentions.append(str(role_id))
            
            if role_mentions:
                embed.add_field(
                    name="Suggested Roles",
                    value="\n".join(role_mentions),
                    inline=False
                )
        
        await interaction.edit_original_response(embed=embed, view=None)
        
        # Notify admins
        await self.notify_admins(interaction)
    
    async def calculate_role_suggestions(self, guild_id: int) -> List[str]:
        """Calculate role suggestions based on answers and rules."""
        suggestions = []
        
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
        
        for rule in rules:
            if self.matches_rule(rule):
                suggestions.extend(rule.suggest_roles)
        
        return list(set(suggestions))  # Remove duplicates
    
    def matches_rule(self, rule: OnboardingRule) -> bool:
        """Check if answers match a rule's conditions."""
        conditions = rule.when_conditions
        
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
        if hasattr(bot, 'config_cache'):
            guild_config = await bot.config_cache.get_guild_config(interaction.guild_id)
            if guild_config and guild_config.logs_channel_id:
                logs_channel = bot.get_channel(guild_config.logs_channel_id)
                if logs_channel:
                    # Get the onboarding session details
                    async with get_session() as session:
                        result = await session.execute(
                            select(OnboardingSession).where(OnboardingSession.id == self.session_id)
                        )
                        onboarding_session = result.scalar_one_or_none()
                        
                        if onboarding_session:
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
                            
                            # Add quick action buttons
                            view = QuickOnboardingActionView(onboarding_session.id)
                            
                            try:
                                await logs_channel.send(embed=embed, view=view)
                            except discord.Forbidden:
                                pass  # No permission to send to logs channel


class SingleSelectView(discord.ui.View):
    """View for single-select questions."""
    
    def __init__(self, wizard: OnboardingWizard, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.wizard = wizard
        self.question = question
        
        # Create select menu with options
        if question.options:
            options = []
            for i, option in enumerate(question.options[:25]):  # Discord limit
                options.append(discord.SelectOption(
                    label=option[:100],  # Discord limit
                    value=option,
                    description=f"Select {option}"
                ))
            
            select = discord.ui.Select(
                placeholder="Choose your answer...",
                options=options
            )
            select.callback = self.select_option
            self.add_item(select)
    
    async def select_option(self, interaction: discord.Interaction):
        """Handle option selection."""
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
            
            if hasattr(interaction, 'response') and not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
            else:
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
        
        for i, session in enumerate(page_sessions):
            user = interaction.guild.get_member(session.user_id)
            user_name = user.display_name if user else f"User {session.user_id}"
            
            answers_preview = []
            for qid, answer in (session.answers or {}).items():
                if len(answers_preview) < 3:  # Show first 3 answers
                    answers_preview.append(f"**{qid}**: {str(answer)[:50]}...")
            
            suggested_roles = session.suggestion or []
            roles_text = f"{len(suggested_roles)} roles suggested" if suggested_roles else "No roles suggested"
            
            embed.add_field(
                name=f"#{start_idx + i + 1} - 👤 {user_name}",
                value=(
                    f"**Completed**: {discord.utils.format_dt(session.completed_at, 'R')}\n"
                    f"**Roles**: {roles_text}\n"
                    f"**Answers**: {chr(10).join(answers_preview) if answers_preview else 'No answers'}"
                ),
                inline=False
            )
        
        # Update buttons
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
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
                label=f"✅ #{start_idx + i + 1}",
                style=discord.ButtonStyle.success,
                custom_id=f"approve_{session.id}"
            )
            approve_button.callback = lambda inter, sess_id=session.id: self.approve_application(inter, sess_id)
            self.add_item(approve_button)
            
            deny_button = discord.ui.Button(
                label=f"❌ #{start_idx + i + 1}",
                style=discord.ButtonStyle.danger,
                custom_id=f"deny_{session.id}"
            )
            deny_button.callback = lambda inter, sess_id=session.id: self.deny_application(inter, sess_id)
            self.add_item(deny_button)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.primary
        )
        refresh_button.callback = self.refresh_queue
        self.add_item(refresh_button)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_queue(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.sessions) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_queue(interaction)
    
    async def refresh_queue(self, interaction: discord.Interaction):
        """Refresh the queue."""
        self.current_page = 0
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
        await view.show_approval_interface(interaction)
    
    async def deny_application(self, interaction: discord.Interaction, session_id: int):
        """Deny an onboarding application."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "deny applications",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = DenialView(session_id)
        await view.show_denial_interface(interaction)


class ApprovalView(discord.ui.View):
    """View for approving onboarding applications."""
    
    def __init__(self, session_id: int):
        super().__init__(timeout=300)
        self.session_id = session_id
        self.selected_roles = []
    
    async def show_approval_interface(self, interaction: discord.Interaction):
        """Show the approval interface."""
        # Load session details
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
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
        
        # Get user
        user = interaction.guild.get_member(onboarding_session.user_id)
        if not user:
            embed = discord.Embed(
                title="❌ User Not Found",
                description="The user who submitted this application is no longer in the server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Show detailed review
        embed = discord.Embed(
            title="✅ Approve Application",
            description=f"Review and approve **{user.display_name}**'s onboarding application.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="User",
            value=f"{user.mention}\n**ID:** {user.id}",
            inline=True
        )
        
        embed.add_field(
            name="Completed",
            value=discord.utils.format_dt(onboarding_session.completed_at, 'R'),
            inline=True
        )
        
        # Show all answers
        if onboarding_session.answers:
            for qid, answer in onboarding_session.answers.items():
                embed.add_field(
                    name=f"📝 {qid}",
                    value=str(answer)[:1024],  # Discord field limit
                    inline=False
                )
        
        # Show suggested roles
        if onboarding_session.suggestion:
            role_mentions = []
            for role_id in onboarding_session.suggestion:
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_mentions.append(role.mention)
                        if str(role_id) not in self.selected_roles:
                            self.selected_roles.append(str(role_id))
                    else:
                        role_mentions.append(f"Role ID: {role_id}")
                except (ValueError, TypeError):
                    role_mentions.append(str(role_id))
            
            if role_mentions:
                embed.add_field(
                    name="🎭 Suggested Roles",
                    value="\n".join(role_mentions),
                    inline=False
                )
        
        # Build view
        self.clear_items()
        
        # Role selection button
        role_select_button = discord.ui.Button(
            label="Select Roles",
            style=discord.ButtonStyle.secondary,
            emoji="🎭"
        )
        role_select_button.callback = self.select_roles
        self.add_item(role_select_button)
        
        # Approve button
        approve_button = discord.ui.Button(
            label="Approve Application",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        approve_button.callback = self.approve_final
        self.add_item(approve_button)
        
        # Cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            emoji="❌"
        )
        cancel_button.callback = self.cancel_approval
        self.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    async def select_roles(self, interaction: discord.Interaction):
        """Open role selection interface."""
        # Get all assignable roles
        assignable_roles = [role for role in interaction.guild.roles 
                           if not role.managed and role != interaction.guild.default_role]
        
        if not assignable_roles:
            embed = discord.Embed(
                title="❌ No Roles Available",
                description="No assignable roles found.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create role selection view
        view = RoleSelectionView(self.selected_roles, assignable_roles)
        await view.show_role_selection(interaction)
    
    async def approve_final(self, interaction: discord.Interaction):
        """Final approval action."""
        # Load session
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
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
        
        # Get user
        user = interaction.guild.get_member(onboarding_session.user_id)
        if not user:
            embed = discord.Embed(
                title="❌ User Not Found",
                description="The user is no longer in the server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Assign roles
        assigned_roles = []
        failed_roles = []
        
        for role_id in self.selected_roles:
            try:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    await user.add_roles(role, reason=f"Onboarding approved by {interaction.user}")
                    assigned_roles.append(role.mention)
                else:
                    failed_roles.append(f"Role ID: {role_id}")
            except (discord.Forbidden, discord.HTTPException, ValueError):
                failed_roles.append(f"Role ID: {role_id}")
        
        # Update session state
        async with get_session() as session:
            await session.execute(
                update(OnboardingSession)
                .where(OnboardingSession.id == self.session_id)
                .values(
                    state='approved',
                    reviewed_at=datetime.utcnow(),
                    reviewed_by=interaction.user.id
                )
            )
            await session.commit()
        
        # Send approval message to user
        try:
            user_embed = discord.Embed(
                title="🎉 Welcome to the Server!",
                description=f"Your onboarding application has been approved by {interaction.user.mention}!",
                color=discord.Color.green()
            )
            
            if assigned_roles:
                user_embed.add_field(
                    name="Assigned Roles",
                    value="\n".join(assigned_roles),
                    inline=False
                )
            
            await user.send(embed=user_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled
        
        # Response to admin
        embed = discord.Embed(
            title="✅ Application Approved",
            description=f"Successfully approved {user.mention}'s onboarding application!",
            color=discord.Color.green()
        )
        
        if assigned_roles:
            embed.add_field(
                name="Assigned Roles",
                value="\n".join(assigned_roles),
                inline=False
            )
        
        if failed_roles:
            embed.add_field(
                name="Failed Role Assignments",
                value="\n".join(failed_roles),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def cancel_approval(self, interaction: discord.Interaction):
        """Cancel approval process."""
        embed = discord.Embed(
            title="❌ Approval Cancelled",
            description="The approval process has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DenialView(discord.ui.View):
    """View for denying onboarding applications."""
    
    def __init__(self, session_id: int):
        super().__init__(timeout=300)
        self.session_id = session_id
    
    async def show_denial_interface(self, interaction: discord.Interaction):
        """Show the denial interface."""
        modal = DenialReasonModal(self.session_id)
        await interaction.response.send_modal(modal)


class DenialReasonModal(discord.ui.Modal):
    """Modal for entering denial reason."""
    
    def __init__(self, session_id: int):
        super().__init__(title="Deny Application")
        self.session_id = session_id
        
        self.reason_input = discord.ui.TextInput(
            label="Reason for Denial",
            placeholder="Enter the reason for denying this application...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle denial submission."""
        reason = self.reason_input.value
        
        # Load session
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession).where(OnboardingSession.id == self.session_id)
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
        
        # Get user
        user = interaction.guild.get_member(onboarding_session.user_id)
        
        # Update session state
        async with get_session() as session:
            await session.execute(
                update(OnboardingSession)
                .where(OnboardingSession.id == self.session_id)
                .values(
                    state='denied',
                    reviewed_at=datetime.utcnow(),
                    reviewed_by=interaction.user.id,
                    denial_reason=reason
                )
            )
            await session.commit()
        
        # Send denial message to user
        if user:
            try:
                user_embed = discord.Embed(
                    title="❌ Application Denied",
                    description=f"Your onboarding application has been denied by {interaction.user.mention}.",
                    color=discord.Color.red()
                )
                
                user_embed.add_field(
                    name="Reason",
                    value=reason,
                    inline=False
                )
                
                user_embed.add_field(
                    name="What's Next?",
                    value="You may contact server administrators if you have questions or would like to reapply.",
                    inline=False
                )
                
                await user.send(embed=user_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled
        
        # Response to admin
        user_mention = user.mention if user else f"User {onboarding_session.user_id}"
        embed = discord.Embed(
            title="❌ Application Denied",
            description=f"Successfully denied {user_mention}'s onboarding application.\n\nReason: {reason}",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleSelectionView(discord.ui.View):
    """View for selecting roles during approval."""
    
    def __init__(self, selected_roles: List[str], available_roles: List[discord.Role]):
        super().__init__(timeout=300)
        self.selected_roles = selected_roles
        self.available_roles = available_roles
    
    async def show_role_selection(self, interaction: discord.Interaction):
        """Show role selection interface."""
        embed = discord.Embed(
            title="🎭 Select Roles",
            description="Choose which roles to assign to the user:",
            color=discord.Color.blue()
        )
        
        # Show currently selected roles
        if self.selected_roles:
            selected_mentions = []
            for role_id in self.selected_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    selected_mentions.append(role.mention)
            
            if selected_mentions:
                embed.add_field(
                    name="Selected Roles",
                    value="\n".join(selected_mentions),
                    inline=False
                )
        else:
            embed.add_field(
                name="Selected Roles",
                value="None selected",
                inline=False
            )
        
        # Create role selection dropdown
        options = []
        for role in self.available_roles[:25]:  # Discord limit
            is_selected = str(role.id) in self.selected_roles
            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"{'✅ Selected' if is_selected else 'Select'} {role.name}",
                default=is_selected
            ))
        
        if options:
            select = discord.ui.Select(
                placeholder="Choose roles to assign...",
                options=options,
                max_values=len(options)
            )
            select.callback = self.role_selected
            self.add_item(select)
        
        # Done button
        done_button = discord.ui.Button(
            label="Done",
            style=discord.ButtonStyle.primary,
            emoji="✅"
        )
        done_button.callback = self.done_selecting
        self.add_item(done_button)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    async def role_selected(self, interaction: discord.Interaction):
        """Handle role selection."""
        selected_values = interaction.data['values']
        self.selected_roles = selected_values
        await self.show_role_selection(interaction)
    
    async def done_selecting(self, interaction: discord.Interaction):
        """Finish role selection."""
        selected_mentions = []
        for role_id in self.selected_roles:
            role = interaction.guild.get_role(int(role_id))
            if role:
                selected_mentions.append(role.mention)
        
        embed = discord.Embed(
            title="✅ Roles Selected",
            description=f"Selected {len(self.selected_roles)} roles for assignment.",
            color=discord.Color.green()
        )
        
        if selected_mentions:
            embed.add_field(
                name="Selected Roles",
                value="\n".join(selected_mentions),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuickOnboardingActionView(discord.ui.View):
    """Quick action buttons for onboarding notifications."""
    
    def __init__(self, session_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.session_id = session_id
        
        review_button = discord.ui.Button(
            label="Review Application",
            style=discord.ButtonStyle.primary,
            emoji="📋",
            custom_id=f"onboarding_review_{session_id}"
        )
        review_button.callback = self.review_application
        self.add_item(review_button)
    
    async def review_application(self, interaction: discord.Interaction):
        """Handle review button click."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "review onboarding applications",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Extract session ID from custom_id
        session_id = int(interaction.data["custom_id"].split("_")[-1])
        
        # Load session
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
        
        # Open detailed review
        view = ApprovalView(session_id)
        await view.show_approval_interface(interaction)