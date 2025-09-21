"""
Configuration management views for the Guild Management Bot
"""
import discord
from sqlalchemy import select, and_, update, delete
from typing import Dict, List, Any, Optional

from database import (
    GuildConfig, OnboardingQuestion, OnboardingRule, 
    get_session
)
from utils.permissions import PermissionChecker, require_admin


def get_config_view(config_type: str):
    """Factory function to get the appropriate configuration view."""
    config_views = {
        'config_guild_basics': GuildBasicsView,
        'config_onboarding_questions': OnboardingQuestionsView,
        'config_onboarding_rules': OnboardingRulesView,
        'config_poll_settings': PollSettingsView,
        'config_moderation': ModerationSettingsView,
        'config_panels': PanelManagementView
    }
    
    view_class = config_views.get(config_type, GuildBasicsView)
    return view_class()


class GuildBasicsView(discord.ui.View):
    """Basic guild configuration settings."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.guild_config = None
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display guild basics settings."""
        await self.load_config(interaction.guild_id)
        
        embed = discord.Embed(
            title="⚙️ Guild Basic Settings",
            description="Configure fundamental guild settings",
            color=discord.Color.blue()
        )
        
        # Default member role
        if self.guild_config.default_member_role_id:
            role = interaction.guild.get_role(self.guild_config.default_member_role_id)
            role_text = role.mention if role else "Role not found"
        else:
            role_text = "Not set"
        embed.add_field(name="Default Member Role", value=role_text, inline=True)
        
        # Welcome channel
        if self.guild_config.welcome_channel_id:
            channel = interaction.guild.get_channel(self.guild_config.welcome_channel_id)
            channel_text = channel.mention if channel else "Channel not found"
        else:
            channel_text = "Not set"
        embed.add_field(name="Welcome Channel", value=channel_text, inline=True)
        
        # Logs channel
        if self.guild_config.logs_channel_id:
            channel = interaction.guild.get_channel(self.guild_config.logs_channel_id)
            channel_text = channel.mention if channel else "Channel not found"
        else:
            channel_text = "Not set"
        embed.add_field(name="Logs Channel", value=channel_text, inline=True)
        
        # Announcements channel
        if self.guild_config.announcements_channel_id:
            channel = interaction.guild.get_channel(self.guild_config.announcements_channel_id)
            channel_text = channel.mention if channel else "Channel not found"
        else:
            channel_text = "Not set"
        embed.add_field(name="Announcements Channel", value=channel_text, inline=True)
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def load_config(self, guild_id: int):
        """Load guild configuration."""
        async with get_session() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            self.guild_config = result.scalar_one_or_none()
            
            if not self.guild_config:
                self.guild_config = GuildConfig(guild_id=guild_id)
                session.add(self.guild_config)
                await session.commit()
                await session.refresh(self.guild_config)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Role selectors
        default_role_select = discord.ui.RoleSelect(
            placeholder="Set default member role...",
            max_values=1
        )
        default_role_select.callback = self.set_default_role
        self.add_item(default_role_select)
        
        # Channel selectors
        welcome_channel_select = discord.ui.ChannelSelect(
            placeholder="Set welcome channel...",
            channel_types=[discord.ChannelType.text],
            max_values=1
        )
        welcome_channel_select.callback = self.set_welcome_channel
        self.add_item(welcome_channel_select)
        
        logs_channel_select = discord.ui.ChannelSelect(
            placeholder="Set logs channel...",
            channel_types=[discord.ChannelType.text],
            max_values=1
        )
        logs_channel_select.callback = self.set_logs_channel
        self.add_item(logs_channel_select)
        
        announcements_channel_select = discord.ui.ChannelSelect(
            placeholder="Set announcements channel...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            max_values=1
        )
        announcements_channel_select.callback = self.set_announcements_channel
        self.add_item(announcements_channel_select)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save All Settings",
            style=discord.ButtonStyle.primary,
            emoji="💾"
        )
        save_button.callback = self.save_settings
        self.add_item(save_button)
    
    async def set_default_role(self, interaction: discord.Interaction):
        """Set default member role."""
        role = interaction.data['resolved']['roles'][interaction.data['values'][0]]
        self.guild_config.default_member_role_id = int(role['id'])
        
        await interaction.response.send_message(
            f"✅ Default member role set to <@&{role['id']}>",
            ephemeral=True
        )
    
    async def set_welcome_channel(self, interaction: discord.Interaction):
        """Set welcome channel."""
        channel = interaction.data['resolved']['channels'][interaction.data['values'][0]]
        self.guild_config.welcome_channel_id = int(channel['id'])
        
        await interaction.response.send_message(
            f"✅ Welcome channel set to <#{channel['id']}>",
            ephemeral=True
        )
    
    async def set_logs_channel(self, interaction: discord.Interaction):
        """Set logs channel."""
        channel = interaction.data['resolved']['channels'][interaction.data['values'][0]]
        self.guild_config.logs_channel_id = int(channel['id'])
        
        await interaction.response.send_message(
            f"✅ Logs channel set to <#{channel['id']}>",
            ephemeral=True
        )
    
    async def set_announcements_channel(self, interaction: discord.Interaction):
        """Set announcements channel."""
        channel = interaction.data['resolved']['channels'][interaction.data['values'][0]]
        self.guild_config.announcements_channel_id = int(channel['id'])
        
        await interaction.response.send_message(
            f"✅ Announcements channel set to <#{channel['id']}>",
            ephemeral=True
        )
    
    async def save_settings(self, interaction: discord.Interaction):
        """Save all settings to database."""
        async with get_session() as session:
            await session.merge(self.guild_config)
            await session.commit()
        
        # Invalidate cache
        bot = interaction.client
        if hasattr(bot, 'config_cache'):
            bot.config_cache.invalidate_guild_config(interaction.guild_id)
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Guild basic settings have been updated successfully!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class OnboardingQuestionsView(discord.ui.View):
    """Onboarding questions configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.questions = []
    
    async def show_questions(self, interaction: discord.Interaction):
        """Display onboarding questions."""
        await self.load_questions(interaction.guild_id)
        
        embed = discord.Embed(
            title="❓ Onboarding Questions",
            description="Manage questions asked during onboarding",
            color=discord.Color.blue()
        )
        
        if not self.questions:
            embed.add_field(
                name="No Questions",
                value="No onboarding questions configured. Click 'Add Question' to create one.",
                inline=False
            )
        else:
            # Pagination
            per_page = 5
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_questions = self.questions[start_idx:end_idx]
            
            for question in page_questions:
                status_emoji = "✅" if question.is_active else "❌"
                required_text = " (Required)" if question.required else " (Optional)"
                
                embed.add_field(
                    name=f"{status_emoji} {question.qid}{required_text}",
                    value=(
                        f"**Type:** {question.type}\n"
                        f"**Prompt:** {question.prompt[:100]}{'...' if len(question.prompt) > 100 else ''}\n"
                        f"**Position:** {question.position}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page + 1} of {(len(self.questions) - 1) // per_page + 1}")
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def load_questions(self, guild_id: int):
        """Load onboarding questions."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion)
                .where(OnboardingQuestion.guild_id == guild_id)
                .order_by(OnboardingQuestion.position)
            )
            self.questions = result.scalars().all()
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Add question button
        add_button = discord.ui.Button(
            label="Add Question",
            style=discord.ButtonStyle.primary,
            emoji="➕"
        )
        add_button.callback = self.add_question
        self.add_item(add_button)
        
        # Question management dropdown
        if self.questions:
            # Show current page questions in dropdown
            per_page = 5
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_questions = self.questions[start_idx:end_idx]
            
            if page_questions:
                options = []
                for question in page_questions:
                    status_emoji = "✅" if question.is_active else "❌"
                    options.append(discord.SelectOption(
                        label=f"{status_emoji} {question.qid}",
                        description=question.prompt[:100],
                        value=str(question.id)
                    ))
                
                question_select = discord.ui.Select(
                    placeholder="Select question to edit...",
                    options=options
                )
                question_select.callback = self.edit_question
                self.add_item(question_select)
        
        # Navigation buttons
        per_page = 5
        if self.current_page > 0:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if (self.current_page + 1) * per_page < len(self.questions):
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
    
    async def add_question(self, interaction: discord.Interaction):
        """Add a new question."""
        modal = AddQuestionModal()
        await interaction.response.send_modal(modal)
    
    async def edit_question(self, interaction: discord.Interaction):
        """Edit a question."""
        question_id = int(interaction.data['values'][0])
        question = next((q for q in self.questions if q.id == question_id), None)
        
        if not question:
            await interaction.response.send_message("Question not found.", ephemeral=True)
            return
        
        view = QuestionEditView(question)
        await view.show_question(interaction)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_questions(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.questions) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_questions(interaction)


class AddQuestionModal(discord.ui.Modal):
    """Modal for adding new onboarding questions."""
    
    def __init__(self):
        super().__init__(title="Add Onboarding Question")
        
        self.qid_input = discord.ui.TextInput(
            label="Question ID",
            placeholder="unique_identifier_for_question",
            required=True,
            max_length=100
        )
        self.add_item(self.qid_input)
        
        self.prompt_input = discord.ui.TextInput(
            label="Question Prompt",
            placeholder="What question do you want to ask?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.prompt_input)
        
        self.map_to_input = discord.ui.TextInput(
            label="Map To Key",
            placeholder="key_for_rules_engine",
            required=True,
            max_length=100
        )
        self.add_item(self.map_to_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle question creation."""
        qid = self.qid_input.value.strip()
        prompt = self.prompt_input.value.strip()
        map_to = self.map_to_input.value.strip()
        
        # Check for duplicate QID
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion).where(
                    and_(
                        OnboardingQuestion.guild_id == interaction.guild_id,
                        OnboardingQuestion.qid == qid
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                embed = discord.Embed(
                    title="❌ Duplicate ID",
                    description=f"A question with ID '{qid}' already exists.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Get next position
            result = await session.execute(
                select(OnboardingQuestion.position)
                .where(OnboardingQuestion.guild_id == interaction.guild_id)
                .order_by(OnboardingQuestion.position.desc())
                .limit(1)
            )
            max_position = result.scalar_one_or_none()
            next_position = (max_position or 0) + 1
            
            # Create question
            question = OnboardingQuestion(
                guild_id=interaction.guild_id,
                qid=qid,
                prompt=prompt,
                type='text',  # Default to text, can be changed later
                required=True,
                map_to=map_to,
                position=next_position
            )
            session.add(question)
            await session.commit()
        
        # Open question settings
        view = QuestionTypeView(qid)
        
        embed = discord.Embed(
            title="✅ Question Created",
            description=f"Question '{qid}' has been created. Now configure its settings:",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class QuestionTypeView(discord.ui.View):
    """View for configuring question type and options."""
    
    def __init__(self, qid: str):
        super().__init__(timeout=300)
        self.qid = qid
    
    @discord.ui.select(
        placeholder="Select question type...",
        options=[
            discord.SelectOption(
                label="Text Input",
                value="text",
                description="Free text response",
                emoji="📝"
            ),
            discord.SelectOption(
                label="Single Select",
                value="single_select",
                description="Choose one option from a list",
                emoji="🔘"
            )
        ]
    )
    async def select_type(self, interaction: discord.Interaction, menu: discord.ui.Select):
        """Select question type."""
        question_type = menu.values[0]
        
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion).where(
                    and_(
                        OnboardingQuestion.guild_id == interaction.guild_id,
                        OnboardingQuestion.qid == self.qid
                    )
                )
            )
            question = result.scalar_one()
            question.type = question_type
            await session.commit()
        
        if question_type == 'single_select':
            # Show options configuration
            modal = QuestionOptionsModal(self.qid)
            await interaction.response.send_modal(modal)
        else:
            embed = discord.Embed(
                title="✅ Question Type Set",
                description=f"Question type set to **{question_type}**.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class QuestionOptionsModal(discord.ui.Modal):
    """Modal for configuring single select options."""
    
    def __init__(self, qid: str):
        super().__init__(title="Configure Options")
        self.qid = qid
        
        self.options_input = discord.ui.TextInput(
            label="Options (one per line)",
            placeholder="Option 1\nOption 2\nOption 3",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.options_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle options configuration."""
        options_text = self.options_input.value.strip()
        options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
        
        if len(options) < 2:
            embed = discord.Embed(
                title="❌ Invalid Options",
                description="Please provide at least 2 options.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion).where(
                    and_(
                        OnboardingQuestion.guild_id == interaction.guild_id,
                        OnboardingQuestion.qid == self.qid
                    )
                )
            )
            question = result.scalar_one()
            question.options = options
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Options Configured",
            description=f"Configured {len(options)} options for the question.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuestionEditView(discord.ui.View):
    """View for editing an existing question."""
    
    def __init__(self, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.question = question
    
    async def show_question(self, interaction: discord.Interaction):
        """Display question details and edit options."""
        embed = discord.Embed(
            title=f"✏️ Edit Question: {self.question.qid}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Prompt", value=self.question.prompt, inline=False)
        embed.add_field(name="Type", value=self.question.type, inline=True)
        embed.add_field(name="Required", value="Yes" if self.question.required else "No", inline=True)
        embed.add_field(name="Position", value=str(self.question.position), inline=True)
        embed.add_field(name="Map To", value=self.question.map_to, inline=True)
        embed.add_field(name="Active", value="Yes" if self.question.is_active else "No", inline=True)
        
        if self.question.options:
            embed.add_field(
                name="Options",
                value="\n".join(f"• {opt}" for opt in self.question.options),
                inline=False
            )
        
        self.update_buttons()
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Toggle active status
        toggle_button = discord.ui.Button(
            label=f"{'Deactivate' if self.question.is_active else 'Activate'}",
            style=discord.ButtonStyle.danger if self.question.is_active else discord.ButtonStyle.success,
            emoji="❌" if self.question.is_active else "✅"
        )
        toggle_button.callback = self.toggle_active
        self.add_item(toggle_button)
        
        # Toggle required status
        required_button = discord.ui.Button(
            label=f"Required: {'ON' if self.question.required else 'OFF'}",
            style=discord.ButtonStyle.success if self.question.required else discord.ButtonStyle.secondary
        )
        required_button.callback = self.toggle_required
        self.add_item(required_button)
        
        # Edit prompt
        edit_button = discord.ui.Button(
            label="Edit Prompt",
            style=discord.ButtonStyle.secondary,
            emoji="✏️"
        )
        edit_button.callback = self.edit_prompt
        self.add_item(edit_button)
        
        # Delete question
        delete_button = discord.ui.Button(
            label="Delete",
            style=discord.ButtonStyle.danger,
            emoji="🗑️"
        )
        delete_button.callback = self.delete_question
        self.add_item(delete_button)
    
    async def toggle_active(self, interaction: discord.Interaction):
        """Toggle question active status."""
        async with get_session() as session:
            await session.execute(
                update(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
                .values(is_active=not self.question.is_active)
            )
            await session.commit()
            self.question.is_active = not self.question.is_active
        
        status = "activated" if self.question.is_active else "deactivated"
        embed = discord.Embed(
            title=f"✅ Question {status.title()}",
            description=f"Question '{self.question.qid}' has been {status}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_question(interaction)
    
    async def toggle_required(self, interaction: discord.Interaction):
        """Toggle question required status."""
        async with get_session() as session:
            await session.execute(
                update(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
                .values(required=not self.question.required)
            )
            await session.commit()
            self.question.required = not self.question.required
        
        status = "required" if self.question.required else "optional"
        embed = discord.Embed(
            title="✅ Requirement Updated",
            description=f"Question '{self.question.qid}' is now {status}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_question(interaction)
    
    async def edit_prompt(self, interaction: discord.Interaction):
        """Edit question prompt."""
        modal = EditPromptModal(self.question)
        await interaction.response.send_modal(modal)
    
    async def delete_question(self, interaction: discord.Interaction):
        """Delete the question."""
        view = ConfirmDeleteQuestionView(self.question)
        
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete question '{self.question.qid}'?\n\nThis action cannot be undone.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class EditPromptModal(discord.ui.Modal):
    """Modal for editing question prompt."""
    
    def __init__(self, question: OnboardingQuestion):
        super().__init__(title="Edit Question Prompt")
        self.question = question
        
        self.prompt_input = discord.ui.TextInput(
            label="Question Prompt",
            default=question.prompt,
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.prompt_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle prompt update."""
        new_prompt = self.prompt_input.value.strip()
        
        async with get_session() as session:
            await session.execute(
                update(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
                .values(prompt=new_prompt)
            )
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Prompt Updated",
            description=f"Question prompt has been updated.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmDeleteQuestionView(discord.ui.View):
    """Confirmation view for question deletion."""
    
    def __init__(self, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.question = question
    
    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm question deletion."""
        async with get_session() as session:
            await session.execute(
                delete(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
            )
            await session.commit()
        
        embed = discord.Embed(
            title="🗑️ Question Deleted",
            description=f"Question '{self.question.qid}' has been deleted.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel deletion."""
        embed = discord.Embed(
            title="❌ Deletion Cancelled",
            description="Question deletion has been cancelled.",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class OnboardingRulesView(discord.ui.View):
    """Onboarding rules configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.rules = []
    
    async def show_rules(self, interaction: discord.Interaction):
        """Display onboarding rules."""
        await self.load_rules(interaction.guild_id)
        
        embed = discord.Embed(
            title="📏 Onboarding Rules",
            description="Rules for suggesting roles based on answers",
            color=discord.Color.blue()
        )
        
        if not self.rules:
            embed.add_field(
                name="No Rules",
                value="No onboarding rules configured. Click 'Add Rule' to create one.",
                inline=False
            )
        else:
            for rule in self.rules:
                status_emoji = "✅" if rule.is_active else "❌"
                conditions_text = []
                
                for condition in rule.when_conditions:
                    conditions_text.append(f"{condition.get('key')} = {condition.get('value')}")
                
                embed.add_field(
                    name=f"{status_emoji} Rule {rule.id}",
                    value=(
                        f"**When:** {' AND '.join(conditions_text)}\n"
                        f"**Suggest:** {len(rule.suggest_roles)} role(s)"
                    ),
                    inline=False
                )
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def load_rules(self, guild_id: int):
        """Load onboarding rules."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingRule)
                .where(OnboardingRule.guild_id == guild_id)
                .order_by(OnboardingRule.id)
            )
            self.rules = result.scalars().all()
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Add rule button
        add_button = discord.ui.Button(
            label="Add Rule",
            style=discord.ButtonStyle.primary,
            emoji="➕"
        )
        add_button.callback = self.add_rule
        self.add_item(add_button)
        
        # Rule management dropdown
        if self.rules and len(self.rules) <= 25:
            options = []
            for rule in self.rules:
                status_emoji = "✅" if rule.is_active else "❌"
                conditions_preview = []
                for condition in rule.when_conditions[:2]:  # Show first 2 conditions
                    conditions_preview.append(f"{condition.get('key')}={condition.get('value')}")
                
                description = f"When: {', '.join(conditions_preview)}"
                if len(rule.when_conditions) > 2:
                    description += "..."
                
                options.append(discord.SelectOption(
                    label=f"{status_emoji} Rule {rule.id}",
                    description=description[:100],
                    value=str(rule.id)
                ))
            
            rule_select = discord.ui.Select(
                placeholder="Select rule to edit...",
                options=options
            )
            rule_select.callback = self.edit_rule
            self.add_item(rule_select)
    
    async def add_rule(self, interaction: discord.Interaction):
        """Add a new rule."""
        modal = AddRuleModal()
        await interaction.response.send_modal(modal)
    
    async def edit_rule(self, interaction: discord.Interaction):
        """Edit a rule."""
        rule_id = int(interaction.data['values'][0])
        rule = next((r for r in self.rules if r.id == rule_id), None)
        
        if not rule:
            await interaction.response.send_message("Rule not found.", ephemeral=True)
            return
        
        view = RuleEditView(rule)
        await view.show_rule(interaction)


class AddRuleModal(discord.ui.Modal):
    """Modal for adding new onboarding rules."""
    
    def __init__(self):
        super().__init__(title="Add Onboarding Rule")
        
        self.condition_input = discord.ui.TextInput(
            label="Condition (key=value)",
            placeholder="experience_level=beginner",
            required=True,
            max_length=200
        )
        self.add_item(self.condition_input)
        
        self.roles_input = discord.ui.TextInput(
            label="Role Names or IDs (one per line)",
            placeholder="Beginner\nNewcomer\n123456789",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rule creation."""
        condition_text = self.condition_input.value.strip()
        roles_text = self.roles_input.value.strip()
        
        # Parse condition
        if '=' not in condition_text:
            embed = discord.Embed(
                title="❌ Invalid Condition",
                description="Condition must be in format 'key=value'",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        key, value = condition_text.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        # Parse roles
        role_names = [role.strip() for role in roles_text.split('\n') if role.strip()]
        
        if not role_names:
            embed = discord.Embed(
                title="❌ No Roles",
                description="Please provide at least one role.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create rule
        async with get_session() as session:
            rule = OnboardingRule(
                guild_id=interaction.guild_id,
                when_conditions=[{"key": key, "value": value}],
                suggest_roles=role_names
            )
            session.add(rule)
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Rule Created",
            description=f"Rule created: When **{key}** = **{value}**, suggest {len(role_names)} role(s).",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RuleEditView(discord.ui.View):
    """View for editing onboarding rules."""
    
    def __init__(self, rule: OnboardingRule):
        super().__init__(timeout=300)
        self.rule = rule
    
    async def show_rule(self, interaction: discord.Interaction):
        """Display rule details."""
        embed = discord.Embed(
            title=f"📏 Edit Rule {self.rule.id}",
            color=discord.Color.blue()
        )
        
        # Show conditions
        conditions_text = []
        for condition in self.rule.when_conditions:
            conditions_text.append(f"**{condition.get('key')}** = **{condition.get('value')}**")
        
        embed.add_field(
            name="Conditions",
            value="\n".join(conditions_text),
            inline=False
        )
        
        # Show suggested roles
        embed.add_field(
            name="Suggested Roles",
            value="\n".join(f"• {role}" for role in self.rule.suggest_roles),
            inline=False
        )
        
        embed.add_field(
            name="Active",
            value="Yes" if self.rule.is_active else "No",
            inline=True
        )
        
        self.update_buttons()
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Toggle active
        toggle_button = discord.ui.Button(
            label=f"{'Deactivate' if self.rule.is_active else 'Activate'}",
            style=discord.ButtonStyle.danger if self.rule.is_active else discord.ButtonStyle.success
        )
        toggle_button.callback = self.toggle_active
        self.add_item(toggle_button)
        
        # Delete rule
        delete_button = discord.ui.Button(
            label="Delete",
            style=discord.ButtonStyle.danger,
            emoji="🗑️"
        )
        delete_button.callback = self.delete_rule
        self.add_item(delete_button)
    
    async def toggle_active(self, interaction: discord.Interaction):
        """Toggle rule active status."""
        async with get_session() as session:
            await session.execute(
                update(OnboardingRule)
                .where(OnboardingRule.id == self.rule.id)
                .values(is_active=not self.rule.is_active)
            )
            await session.commit()
            self.rule.is_active = not self.rule.is_active
        
        status = "activated" if self.rule.is_active else "deactivated"
        embed = discord.Embed(
            title=f"✅ Rule {status.title()}",
            description=f"Rule {self.rule.id} has been {status}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def delete_rule(self, interaction: discord.Interaction):
        """Delete the rule."""
        async with get_session() as session:
            await session.execute(
                delete(OnboardingRule)
                .where(OnboardingRule.id == self.rule.id)
            )
            await session.commit()
        
        embed = discord.Embed(
            title="🗑️ Rule Deleted",
            description=f"Rule {self.rule.id} has been deleted.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class PollSettingsView(discord.ui.View):
    """Poll settings configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display poll settings."""
        embed = discord.Embed(
            title="📊 Poll Settings",
            description="Configure default poll settings",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Default Duration",
            value="24 hours",
            inline=True
        )
        
        embed.add_field(
            name="Anonymous Default",
            value="No",
            inline=True
        )
        
        embed.add_field(
            name="Creator Roles",
            value="Admin only",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class ModerationSettingsView(discord.ui.View):
    """Moderation settings configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display moderation settings."""
        embed = discord.Embed(
            title="🛡️ Moderation Settings",
            description="Configure auto-moderation features",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Spam Filter",
            value="🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Swear Filter",
            value="🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Watch Channels",
            value="None configured",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class PanelManagementView(discord.ui.View):
    """Panel deployment and management."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Deploy Admin Dashboard in channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def deploy_admin_dashboard(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy admin dashboard."""
        picked = menu.values[0]
        channel = interaction.guild.get_channel(picked.id) or await interaction.guild.fetch_channel(picked.id)
        
        from views.panels import AdminDashboard
        
        embed = discord.Embed(
            title="🎛️ Admin Dashboard",
            description="Administrative control panel for server management",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Features",
            value=(
                "• Onboarding queue management\n"
                "• Announcement system\n"
                "• Role and promotion tools\n"
                "• Poll creation and management\n"
                "• Moderation settings\n"
                "• Profile administration\n"
                "• Server configuration"
            ),
            inline=False
        )
        
        embed.set_footer(text="This panel is only visible to administrators")
        
        try:
            dashboard_view = AdminDashboard()
            message = await channel.send(embed=embed, view=dashboard_view)
            
            # Update guild config with dashboard location
            async with get_session() as session:
                result = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
                )
                guild_config = result.scalar_one_or_none()
                
                if not guild_config:
                    guild_config = GuildConfig(guild_id=interaction.guild_id)
                    session.add(guild_config)
                
                guild_config.admin_dashboard_channel_id = channel.id
                guild_config.admin_dashboard_message_id = message.id
                await session.commit()
            
            response_embed = discord.Embed(
                title="✅ Admin Dashboard Deployed",
                description=f"Admin dashboard has been deployed in {channel.mention}",
                color=discord.Color.green()
            )
            
        except discord.Forbidden:
            response_embed = discord.Embed(
                title="❌ Permission Error",
                description=f"I don't have permission to send messages in {channel.mention}",
                color=discord.Color.red()
            )
        except Exception as e:
            response_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to deploy dashboard: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Deploy Member Hub in channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def deploy_member_hub(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy member hub."""
        selected = menu.values[0]
        channel = interaction.guild.get_channel(selected.id) or await interaction.guild.fetch_channel(selected.id)

        
        from views.panels import MemberHub
        
        embed = discord.Embed(
            title="🏠 Member Hub",
            description=f"Welcome to **{interaction.guild.name}**! Your gateway to community features.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🚀 Getting Started",
            value=(
                "• Complete the **onboarding process** to get your roles\n"
                "• Set up your **character profile** to introduce yourself\n"
                "• Create **polls** to engage with the community\n"
                "• **Report** any inappropriate content you encounter"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📚 Resources",
            value=(
                "• **Server Info & Rules** - Learn about our community\n"
                "• **Character Management** - Manage your gaming profiles\n"
                "• **Community Tools** - Polls, events, and more"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to access features")
        
        try:
            hub_view = MemberHub()
            message = await channel.send(embed=embed, view=hub_view)
            
            # Update guild config with hub location
            async with get_session() as session:
                result = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
                )
                guild_config = result.scalar_one_or_none()
                
                if not guild_config:
                    guild_config = GuildConfig(guild_id=interaction.guild_id)
                    session.add(guild_config)
                
                guild_config.member_hub_channel_id = channel.id
                guild_config.member_hub_message_id = message.id
                await session.commit()
            
            response_embed = discord.Embed(
                title="✅ Member Hub Deployed",
                description=f"Member hub has been deployed in {channel.mention}",
                color=discord.Color.green()
            )
            
        except discord.Forbidden:
            response_embed = discord.Embed(
                title="❌ Permission Error",
                description=f"I don't have permission to send messages in {channel.mention}",
                color=discord.Color.red()
            )
        except Exception as e:
            response_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to deploy hub: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=response_embed, ephemeral=True)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display panel management interface."""
        embed = discord.Embed(
            title="🎛️ Panel Management",
            description="Deploy and manage bot control panels",
            color=discord.Color.blue()
        )
        
        # Check current panel locations
        async with get_session() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            guild_config = result.scalar_one_or_none()
        
        if guild_config:
            if guild_config.admin_dashboard_channel_id:
                channel = interaction.guild.get_channel(guild_config.admin_dashboard_channel_id)
                channel_text = channel.mention if channel else "Channel not found"
                embed.add_field(name="Admin Dashboard", value=channel_text, inline=True)
            else:
                embed.add_field(name="Admin Dashboard", value="Not deployed", inline=True)
            
            if guild_config.member_hub_channel_id:
                channel = interaction.guild.get_channel(guild_config.member_hub_channel_id)
                channel_text = channel.mention if channel else "Channel not found"
                embed.add_field(name="Member Hub", value=channel_text, inline=True)
            else:
                embed.add_field(name="Member Hub", value="Not deployed", inline=True)
        else:
            embed.add_field(name="Admin Dashboard", value="Not deployed", inline=True)
            embed.add_field(name="Member Hub", value="Not deployed", inline=True)
        
        embed.add_field(
            name="📝 Instructions",
            value=(
                "1. Use the channel selectors above to deploy panels\n"
                "2. Admin Dashboard should go in a staff-only channel\n"
                "3. Member Hub should go in a public welcome/general channel\n"
                "4. Only one panel of each type can be active at a time"
            ),
            inline=False
        )
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)