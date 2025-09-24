"""
Configuration management views for the Guild Management Bot - FIXED VERSION
"""
from datetime import datetime, timezone
from typing import List, Optional, cast

import discord
from discord import InteractionResponse
from sqlalchemy import select, update, delete

from database import (
    GuildConfig, OnboardingQuestion, get_session
)
from utils.constants import QUESTION_TYPES, COMMON_MAPPINGS, TIMEZONES, MO2_RACES, MO2_ARCHETYPES
from utils.permissions import PermissionChecker


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


class ConfigurationView(discord.ui.View):
    """Main configuration interface."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_configuration_menu(self, interaction: discord.Interaction):
        """Show the main configuration menu."""
        embed = discord.Embed(
            title="⚙️ Configuration Menu",
            description="Manage all bot settings for your server",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Available Sections",
            value="• Guild Basics\n• Onboarding Questions\n• Onboarding Rules\n• Poll Settings\n• Moderation\n• Panel Management",
            inline=False
        )

        response = cast(InteractionResponse, interaction.response)
        await response.send_message(embed=embed, view=self, ephemeral=True)


class GuildBasicsView(discord.ui.View):
    """Basic guild configuration settings."""

    def __init__(self):
        super().__init__(timeout=300)
        self.guild_config: Optional[GuildConfig] = None

    async def show_settings(self, interaction: discord.Interaction):
        """Display basic guild settings."""
        await self.load_config(interaction.guild_id)

        embed = discord.Embed(
            title="🔧 Basic Guild Settings",
            description="Configure essential channels and roles",
            color=discord.Color.blue()
        )

        if self.guild_config:
            # Welcome Channel
            welcome_channel = interaction.guild.get_channel(self.guild_config.welcome_channel_id) if self.guild_config.welcome_channel_id else None
            embed.add_field(
                name="Welcome Channel",
                value=welcome_channel.mention if welcome_channel else "Not set",
                inline=True
            )

            # Logs Channel
            logs_channel = interaction.guild.get_channel(self.guild_config.logs_channel_id) if self.guild_config.logs_channel_id else None
            embed.add_field(
                name="Logs Channel",
                value=logs_channel.mention if logs_channel else "Not set",
                inline=True
            )

            # Announcements Channel
            announcements_channel = interaction.guild.get_channel(self.guild_config.announcements_channel_id) if self.guild_config.announcements_channel_id else None
            embed.add_field(
                name="Announcements Channel",
                value=announcements_channel.mention if announcements_channel else "Not set",
                inline=True
            )

            # Rules Channel
            rules_channel = interaction.guild.get_channel(self.guild_config.rules_channel_id) if self.guild_config.rules_channel_id else None
            embed.add_field(
                name="Rules Channel",
                value=rules_channel.mention if rules_channel else "Not set",
                inline=True
            )

            # General Channel
            general_channel = interaction.guild.get_channel(self.guild_config.general_channel_id) if self.guild_config.general_channel_id else None
            embed.add_field(
                name="General Channel",
                value=general_channel.mention if general_channel else "Not set",
                inline=True
            )

            # Default Member Role
            member_role = interaction.guild.get_role(self.guild_config.default_member_role_id) if self.guild_config.default_member_role_id else None
            embed.add_field(
                name="Default Member Role",
                value=member_role.mention if member_role else "Not set",
                inline=True
            )

            # Timezone
            offset_hours = self.guild_config.timezone_offset
            offset_str = f"UTC{'+' if offset_hours >= 0 else ''}{offset_hours}:00" if offset_hours != 0 else "UTC+00:00"
            embed.add_field(
                name="Server Timezone",
                value=offset_str,
                inline=True
            )
        else:
            embed.add_field(
                name="Status",
                value="Settings will be created when changed.",
                inline=False
            )

        response = cast(InteractionResponse, interaction.response)
        await response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_config(self, guild_id: int):
        """Load guild configuration from database."""
        async with get_session() as session:
            self.guild_config = await session.get(GuildConfig, guild_id)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Set welcome channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def set_welcome_channel(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Set the welcome channel."""
        channel = menu.values[0]
        await self.update_config(interaction, welcome_channel_id=channel.id)

        embed = discord.Embed(
            title="✅ Welcome Channel Set",
            description=f"Welcome channel has been set to {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Set Logs Channel", style=discord.ButtonStyle.secondary, emoji="📋") # type: ignore[arg-type]
    async def set_logs_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show logs channel selection."""
        view = ChannelSelectionView("logs", self)
        embed = discord.Embed(
            title="📋 Select Logs Channel",
            description="Choose a channel for bot logs and audit trails",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Set Announcements Channel", style=discord.ButtonStyle.secondary, emoji="📢") # type: ignore[arg-type]
    async def set_announcements_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show announcements channel selection."""
        view = ChannelSelectionView("announcements", self)
        embed = discord.Embed(
            title="📢 Select Announcements Channel",
            description="Choose a channel for server announcements",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Set Rules Channel", style=discord.ButtonStyle.secondary, emoji="📜") # type: ignore[arg-type]
    async def set_rules_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show rules channel selection."""
        view = ChannelSelectionView("rules", self)
        embed = discord.Embed(
            title="📜 Select Rules Channel",
            description="Choose a channel that contains server rules",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Set General Channel", style=discord.ButtonStyle.secondary, emoji="💬") # type: ignore[arg-type]
    async def set_general_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show general channel selection."""
        view = ChannelSelectionView("general", self)
        embed = discord.Embed(
            title="💬 Select General Channel",
            description="Choose the main general discussion channel",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Set Member Role", style=discord.ButtonStyle.secondary, emoji="🎭", row=1) # type: ignore[arg-type]
    async def set_member_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show member role selection."""
        view = RoleSelectionView(self)
        embed = discord.Embed(
            title="🎭 Select Default Member Role",
            description="Choose the role given to new approved members",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Set Timezone", style=discord.ButtonStyle.secondary, emoji="🌍", row=1) # type: ignore[arg-type]
    async def set_timezone_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show timezone selection."""
        view = TimezoneSelectionView(self)
        embed = discord.Embed(
            title="🌍 Select Server Timezone",
            description="Choose the primary timezone for your server",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def update_config(self, interaction: discord.Interaction, **kwargs):
        """Update guild configuration."""
        async with get_session() as session:
            if not self.guild_config:
                self.guild_config = GuildConfig(guild_id=interaction.guild_id)
                session.add(self.guild_config)

            for key, value in kwargs.items():
                setattr(self.guild_config, key, value)

            self.guild_config.updated_at = datetime.now(timezone.utc)
            await session.commit()


class ChannelSelectionView(discord.ui.View):
    """View for selecting channels."""

    def __init__(self, channel_type: str, parent_view: GuildBasicsView):
        super().__init__(timeout=300)
        self.channel_type = channel_type
        self.parent_view = parent_view

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select a channel...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def select_channel(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Handle channel selection."""
        channel = menu.values[0]
        field_name = f"{self.channel_type}_channel_id"

        await self.parent_view.update_config(interaction, **{field_name: channel.id})

        embed = discord.Embed(
            title=f"✅ {self.channel_type.title()} Channel Set",
            description=f"{self.channel_type.title()} channel has been set to {channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleSelectionView(discord.ui.View):
    """View for selecting roles."""

    def __init__(self, parent_view: GuildBasicsView):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select a role...",
        max_values=1
    )
    async def select_role(self, interaction: discord.Interaction, menu: discord.ui.RoleSelect):
        """Handle role selection."""
        role = menu.values[0]

        if role.is_default():
            await interaction.response.send_message("Cannot set @everyone as default member role.", ephemeral=True)
            return

        await self.parent_view.update_config(interaction, default_member_role_id=role.id)

        embed = discord.Embed(
            title="✅ Default Member Role Set",
            description=f"Default member role has been set to {role.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TimezoneSelectionView(discord.ui.View):
    """View for selecting timezone."""

    def __init__(self, parent_view: GuildBasicsView):
        super().__init__(timeout=300)
        self.parent_view = parent_view

        # Create timezone options
        options = []
        for tz in TIMEZONES[:25]:  # Discord limit
            offset = tz.replace("UTC", "")
            hours = int(offset.split(":")[0]) if ":" in offset else 0

            options.append(discord.SelectOption(
                label=tz,
                value=str(hours),
                description=f"UTC offset: {offset}"
            ))

        select = discord.ui.Select(
            placeholder="Select timezone...",
            options=options
        )
        select.callback = self.select_timezone
        self.add_item(select)

    async def select_timezone(self, interaction: discord.Interaction):
        """Handle timezone selection."""
        offset_hours = int(interaction.data['values'][0])

        await self.parent_view.update_config(interaction, timezone_offset=offset_hours)

        offset_str = f"UTC{'+' if offset_hours >= 0 else ''}{offset_hours}:00"
        embed = discord.Embed(
            title="✅ Timezone Set",
            description=f"Server timezone has been set to {offset_str}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class OnboardingQuestionsView(discord.ui.View):
    """Manage onboarding questions."""

    def __init__(self):
        super().__init__(timeout=300)
        self.questions: List[OnboardingQuestion] = []

    async def show_questions(self, interaction: discord.Interaction):
        """Display onboarding questions."""
        await self.load_questions(interaction.guild_id)

        embed = discord.Embed(
            title="❓ Onboarding Questions",
            description="Manage questions for new member onboarding",
            color=discord.Color.blue()
        )

        if not self.questions:
            embed.add_field(
                name="No Questions",
                value="No onboarding questions configured. Click 'Add Question' to create one.",
                inline=False
            )
        else:
            for i, question in enumerate(self.questions[:10], 1):
                status = "✅ Active" if question.is_active else "❌ Inactive"
                type_display = dict(QUESTION_TYPES).get(question.type, question.type)

                embed.add_field(
                    name=f"Question {i} ({type_display}) - {status}",
                    value=f"{question.prompt[:100]}{'...' if len(question.prompt) > 100 else ''}",
                    inline=False
                )

        # Add mandatory timezone question if missing
        has_timezone = any(q.type == "timezone" for q in self.questions)
        if not has_timezone:
            embed.add_field(
                name="⚠️ Missing Required Question",
                value="A timezone question is required for proper onboarding. Click 'Add Required Questions' to add it.",
                inline=False
            )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_questions(self, guild_id: int):
        """Load questions from database."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion)
                .where(OnboardingQuestion.guild_id == guild_id)
                .order_by(OnboardingQuestion.position)
            )
            self.questions = result.scalars().all()

    @discord.ui.button(label="Add Question", style=discord.ButtonStyle.primary, emoji="➕") # type: ignore[arg-type]
    async def add_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new onboarding question."""
        modal = QuestionCreationModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Required Questions", style=discord.ButtonStyle.secondary, emoji="⚡") # type: ignore[arg-type]
    async def add_required_questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add required questions automatically."""
        await self.load_questions(interaction.guild_id)

        has_timezone = any(q.type == "timezone" for q in self.questions)

        if has_timezone:
            await interaction.response.send_message("All required questions are already present.", ephemeral=True)
            return

        async with get_session() as session:
            # Get next position
            last_position = max([q.position for q in self.questions], default=0)

            # Add mandatory timezone question
            timezone_question = OnboardingQuestion(
                guild_id=interaction.guild_id,
                qid="timezone_required",
                prompt="What is your timezone? This helps us coordinate events and activities.",
                type="timezone",
                required=True,
                options=TIMEZONES,
                map_to="user_timezone",
                position=last_position + 1,
                is_active=True
            )

            session.add(timezone_question)
            await session.commit()

        embed = discord.Embed(
            title="✅ Required Questions Added",
            description="Added mandatory timezone question to your onboarding process.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Edit Questions", style=discord.ButtonStyle.secondary, emoji="✏️") # type: ignore[arg-type]
    async def edit_questions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit existing questions."""
        if not self.questions:
            await interaction.response.send_message("No questions to edit. Create some questions first.", ephemeral=True)
            return

        view = QuestionEditView(self.questions)
        await view.show_question_list(interaction)


class QuestionCreationModal(discord.ui.Modal):
    """Modal for creating onboarding questions - FIXED VERSION."""

    def __init__(self):
        super().__init__(title="Create Onboarding Question")

        self.prompt_input = discord.ui.TextInput(
            label="Question Prompt",
            placeholder="Enter the question you want to ask new members...",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=500
        )

        # Create mapping input with suggestions
        mapping_placeholder = f"Suggested: {', '.join(COMMON_MAPPINGS[:5])}"
        self.mapping_input = discord.ui.TextInput(
            label="Map To (for rules engine)",
            placeholder=mapping_placeholder,
            required=False,
            max_length=100
        )

        self.add_item(self.prompt_input)
        self.add_item(self.mapping_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle question creation."""
        prompt = self.prompt_input.value.strip()
        map_to = self.mapping_input.value.strip() or None

        # Show question type selection
        view = QuestionTypeSelectionView(prompt, map_to)

        embed = discord.Embed(
            title="🎯 Select Question Type",
            description=f"**Question:** {prompt}\n\nChoose the type of question:",
            color=discord.Color.blue()
        )

        # Add descriptions for each type
        type_descriptions = []
        for value, display in QUESTION_TYPES:
            if value == "text":
                desc = "Free text input"
            elif value == "single_select":
                desc = "Choose one option from a list"
            elif value == "multi_select":
                desc = "Choose multiple options from a list"
            elif value == "timezone":
                desc = "Select from timezone list"
            elif value == "race":
                desc = "Select from MO2 character races"
            elif value == "archetype":
                desc = "Select from MO2 character archetypes"
            elif value == "profession":
                desc = "Select from MO2 professions/skills"
            else:
                desc = display

            type_descriptions.append(f"**{display}**: {desc}")

        embed.add_field(
            name="Available Types",
            value="\n".join(type_descriptions),
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class QuestionTypeSelectionView(discord.ui.View):
    """View for selecting question type - FIXED VERSION."""

    def __init__(self, prompt: str, map_to: Optional[str]):
        super().__init__(timeout=300)
        self.prompt = prompt
        self.map_to = map_to

        # Create dropdown with all question types
        options = []
        for value, display in QUESTION_TYPES:
            options.append(discord.SelectOption(
                label=display,
                value=value,
                description=f"Create a {display.lower()} question"
            ))

        select = discord.ui.Select(
            placeholder="Choose question type...",
            options=options
        )
        select.callback = self.select_type
        self.add_item(select)

    async def select_type(self, interaction: discord.Interaction):
        """Handle question type selection."""
        question_type = interaction.data['values'][0]

        # Check if this type needs additional options
        if question_type in ["single_select", "multi_select"]:
            modal = QuestionOptionsModal(self.prompt, question_type, self.map_to)
            await interaction.response.send_modal(modal)
        else:
            # Create the question directly
            await self.create_question(interaction, question_type, None)

    async def create_question(self, interaction: discord.Interaction, question_type: str, options: Optional[List[str]]):
        """Create the question in database."""
        # Set appropriate options based on type
        if question_type == "timezone":
            options = TIMEZONES
        elif question_type == "race":
            options = MO2_RACES
        elif question_type == "archetype":
            options = list(MO2_ARCHETYPES.keys())
        elif question_type == "profession":
            from utils.constants import MO2_PROFESSIONS
            options = MO2_PROFESSIONS

        async with get_session() as session:
            # Get next position
            result = await session.execute(
                select(OnboardingQuestion)
                .where(OnboardingQuestion.guild_id == interaction.guild_id)
                .order_by(OnboardingQuestion.position.desc())
                .limit(1)
            )
            last_question = result.scalar_one_or_none()
            position = (last_question.position + 1) if last_question else 1

            # Create question
            question = OnboardingQuestion(
                guild_id=interaction.guild_id,
                qid=f"q{position}",
                prompt=self.prompt,
                type=question_type,
                required=True,
                options=options if options else None,
                map_to=self.map_to or f"question_{position}",  # FIXED: Always provide a map_to value
                position=position,
                is_active=True
            )

            session.add(question)
            await session.commit()

        type_display = dict(QUESTION_TYPES).get(question_type, question_type)
        embed = discord.Embed(
            title="✅ Question Created",
            description=f"Successfully created {type_display.lower()} question at position {position}",
            color=discord.Color.green()
        )

        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


class QuestionOptionsModal(discord.ui.Modal):
    """Modal for setting question options."""

    def __init__(self, prompt: str, question_type: str, map_to: Optional[str]):
        super().__init__(title="Set Question Options")
        self.prompt = prompt
        self.question_type = question_type
        self.map_to = map_to

        self.options_input = discord.ui.TextInput(
            label="Options (one per line)",
            placeholder="Option 1\nOption 2\nOption 3\n...",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=1000
        )

        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle options submission."""
        options_text = self.options_input.value.strip()
        options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]

        if not options:
            await interaction.response.send_message("Please provide at least one option.", ephemeral=True)
            return

        view = QuestionTypeSelectionView(self.prompt, self.map_to)
        await view.create_question(interaction, self.question_type, options)


class QuestionEditView(discord.ui.View):
    """View for editing existing questions."""

    def __init__(self, questions: List[OnboardingQuestion]):
        super().__init__(timeout=300)
        self.questions = questions

        # Create select menu for questions
        options = []
        for question in questions[:25]:  # Discord limit
            status = "✅" if question.is_active else "❌"
            type_display = dict(QUESTION_TYPES).get(question.type, question.type)

            options.append(discord.SelectOption(
                label=f"{status} {question.prompt[:50]}...",
                description=f"Position {question.position} - {type_display}",
                value=str(question.id),
                emoji="❓"
            ))

        if options:
            select = discord.ui.Select(
                placeholder="Select question to edit...",
                options=options
            )
            select.callback = self.select_question
            self.add_item(select)

    async def show_question_list(self, interaction: discord.Interaction):
        """Show the question list for editing."""
        embed = discord.Embed(
            title="✏️ Edit Questions",
            description="Select a question to edit or manage",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def select_question(self, interaction: discord.Interaction):
        """Handle question selection for editing."""
        question_id = int(interaction.data['values'][0])
        question = next((q for q in self.questions if q.id == question_id), None)

        if not question:
            await interaction.response.send_message("Question not found.", ephemeral=True)
            return

        view = QuestionActionView(question)

        type_display = dict(QUESTION_TYPES).get(question.type, question.type)
        embed = discord.Embed(
            title="✏️ Edit Question",
            color=discord.Color.blue()
        )

        embed.add_field(name="Prompt", value=question.prompt, inline=False)
        embed.add_field(name="Type", value=type_display, inline=True)
        embed.add_field(name="Position", value=str(question.position), inline=True)
        embed.add_field(name="Status", value="Active" if question.is_active else "Inactive", inline=True)

        if question.options:
            options_text = "\n".join(question.options) if isinstance(question.options, list) else str(question.options)
            embed.add_field(name="Options", value=options_text[:1000], inline=False)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class QuestionActionView(discord.ui.View):
    """Actions for a specific question."""

    def __init__(self, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.question = question

        # Toggle activation button
        if question.is_active:
            self.toggle_button = discord.ui.Button(
                label="Deactivate",
                style=discord.ButtonStyle.danger, # type: ignore[arg-type]
                emoji="❌"
            )
        else:
            self.toggle_button = discord.ui.Button(
                label="Activate",
                style=discord.ButtonStyle.success, # type: ignore[arg-type]
                emoji="✅"
            )

        self.toggle_button.callback = self.toggle_active
        self.add_item(self.toggle_button)

    @discord.ui.button(label="Edit Prompt", style=discord.ButtonStyle.secondary, emoji="✏️") # type: ignore[arg-type]
    async def edit_prompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit question prompt."""
        modal = EditPromptModal(self.question)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def delete_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the question."""
        view = DeleteConfirmationView(self.question)

        embed = discord.Embed(
            title="⚠️ Delete Question",
            description=f"Are you sure you want to delete this question?\n\n**{self.question.prompt}**\n\nThis action cannot be undone.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def toggle_active(self, interaction: discord.Interaction):
        """Toggle question active status."""
        new_status = not self.question.is_active

        async with get_session() as session:
            await session.execute(
                update(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
                .values(is_active=new_status, updated_at=datetime.now(timezone.utc))
            )
            await session.commit()

        status_text = "activated" if new_status else "deactivated"
        embed = discord.Embed(
            title=f"✅ Question {status_text.title()}",
            description=f"Question has been {status_text}.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditPromptModal(discord.ui.Modal):
    """Modal for editing question prompt."""

    def __init__(self, question: OnboardingQuestion):
        super().__init__(title="Edit Question Prompt")
        self.question = question

        self.prompt_input = discord.ui.TextInput(
            label="Question Prompt",
            default=question.prompt,
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=500
        )

        self.mapping_input = discord.ui.TextInput(
            label="Map To (for rules engine)",
            default=question.map_to or "",
            required=False,
            max_length=100
        )

        self.add_item(self.prompt_input)
        self.add_item(self.mapping_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle prompt edit submission."""
        new_prompt = self.prompt_input.value.strip()
        new_mapping = self.mapping_input.value.strip() or None

        async with get_session() as session:
            await session.execute(
                update(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
                .values(
                    prompt=new_prompt,
                    map_to=new_mapping,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await session.commit()

        embed = discord.Embed(
            title="✅ Question Updated",
            description="Question prompt has been updated successfully.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class DeleteConfirmationView(discord.ui.View):
    """Confirmation view for question deletion."""

    def __init__(self, question: OnboardingQuestion):
        super().__init__(timeout=300)
        self.question = question

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm question deletion."""
        async with get_session() as session:
            await session.execute(
                delete(OnboardingQuestion)
                .where(OnboardingQuestion.id == self.question.id)
            )
            await session.commit()

        embed = discord.Embed(
            title="✅ Question Deleted",
            description="Question has been permanently deleted.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌") # type: ignore[arg-type]
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel question deletion."""
        embed = discord.Embed(
            title="❌ Deletion Cancelled",
            description="Question deletion cancelled.",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# Additional configuration views (simplified versions)

class OnboardingRulesView(discord.ui.View):
    """Manage onboarding rules."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_rules(self, interaction: discord.Interaction):
        """Display onboarding rules."""
        embed = discord.Embed(
            title="📋 Onboarding Rules",
            description="Configure role assignment rules based on answers",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Coming Soon",
            value="Rule-based role assignment will be implemented in a future update.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class PollSettingsView(discord.ui.View):
    """Poll configuration settings."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_settings(self, interaction: discord.Interaction):
        """Display poll settings."""
        embed = discord.Embed(
            title="📊 Poll Settings",
            description="Configure poll creation permissions and defaults",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Who Can Create Polls",
            value="Currently: All members",
            inline=True
        )

        embed.add_field(
            name="Default Duration",
            value="24 hours",
            inline=True
        )

        embed.add_field(
            name="Max Options",
            value="10 options",
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class ModerationSettingsView(discord.ui.View):
    """Moderation configuration settings."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_settings(self, interaction: discord.Interaction):
        """Display moderation settings."""
        embed = discord.Embed(
            title="🛡️ Moderation Settings",
            description="Configure auto-moderation and logging",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Message Logging",
            value="✅ Enabled - All messages are logged for audit purposes",
            inline=False
        )

        embed.add_field(
            name="Auto-Moderation",
            value="Configure spam and content filters",
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class PanelManagementView(discord.ui.View):
    """Panel deployment and management."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_settings(self, interaction: discord.Interaction):
        """Display panel management interface."""
        embed = discord.Embed(
            title="📋 Panel Management",
            description="Deploy and manage bot control panels",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Admin Dashboard",
            value="Deploy the admin control panel",
            inline=True
        )

        embed.add_field(
            name="Member Hub",
            value="Deploy the member interface panel",
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Deploy Admin Dashboard", style=discord.ButtonStyle.primary, emoji="🎛️") # type: ignore[arg-type]
    async def deploy_admin_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deploy admin dashboard."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "deploy admin dashboard",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = AdminDashboardChannelView()
        embed = discord.Embed(
            title="🎛️ Deploy Admin Dashboard",
            description="Select a channel for the admin dashboard",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Deploy Member Hub", style=discord.ButtonStyle.secondary, emoji="👥") # type: ignore[arg-type]
    async def deploy_member_hub(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deploy member hub."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "deploy member hub",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = MemberHubChannelView()
        embed = discord.Embed(
            title="👥 Deploy Member Hub",
            description="Select a channel for the member hub",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AdminDashboardChannelView(discord.ui.View):
    """Channel selection for admin dashboard."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select channel for admin dashboard...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def select_channel(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy admin dashboard to selected channel."""
        channel = menu.values[0]

        try:
            from views.panels import AdminDashboard

            embed = discord.Embed(
                title="🎛️ Guild Management Admin Dashboard",
                description="Central control panel for server administrators",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Available Functions",
                value="• Onboarding Queue\n• Announcements\n• Role Management\n• Poll Management\n• Moderation Center\n• Profile Administration\n• Configuration",
                inline=False
            )

            view = AdminDashboard()
            message = await channel.send(embed=embed, view=view)

            # Save dashboard location
            from database import create_or_update_guild_config
            await create_or_update_guild_config(
                interaction.guild_id,
                admin_dashboard_channel_id=channel.id,
                admin_dashboard_message_id=message.id
            )

            response_embed = discord.Embed(
                title="✅ Admin Dashboard Deployed",
                description=f"Admin dashboard deployed in {channel.mention}",
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


class MemberHubChannelView(discord.ui.View):
    """Channel selection for member hub."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select channel for member hub...",
        channel_types=[discord.ChannelType.text],
        max_values=1
    )
    async def select_channel(self, interaction: discord.Interaction, menu: discord.ui.ChannelSelect):
        """Deploy member hub to selected channel."""
        channel = menu.values[0]

        try:
            from views.panels import MemberHub

            embed = discord.Embed(
                title="👥 Guild Member Hub",
                description="Your gateway to guild features and activities",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Available Features",
                value="• Start Onboarding\n• Manage Characters\n• Create Polls\n• Report Messages\n• Server Information",
                inline=False
            )

            view = MemberHub()
            message = await channel.send(embed=embed, view=view)

            # Save hub location
            from database import create_or_update_guild_config
            await create_or_update_guild_config(
                interaction.guild_id,
                member_hub_channel_id=channel.id,
                member_hub_message_id=message.id
            )

            response_embed = discord.Embed(
                title="✅ Member Hub Deployed",
                description=f"Member hub deployed in {channel.mention}",
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


# This is the PanelDeploymentView that was referenced in panels.py but didn't exist
# It's now an alias to PanelManagementView for compatibility
class PanelDeploymentView(PanelManagementView):
    """Panel deployment view - alias for PanelManagementView."""

    async def show_deployment_options(self, interaction: discord.Interaction):
        """Show deployment options - delegates to show_settings."""
        await self.show_settings(interaction)