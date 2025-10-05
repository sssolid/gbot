# File: cogs/admin.py
# Location: /bot/cogs/admin.py

import discord
from discord.ext import commands
from discord import app_commands
import logging

from sqlalchemy import text

from models import (
    Guild, ChannelRegistry, RoleRegistry, Question, QuestionOption,
    Game, Configuration, RoleTier, QuestionType
)
from database import db
from utils.helpers import create_embed, set_channel, set_role

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Administrative commands for bot configuration"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin_help", description="View admin commands")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def admin_help(self, interaction: discord.Interaction):
        """Show admin help"""
        if not await self._check_admin(interaction):
            return

        embed = await create_embed(
            title="🛠️ Admin Commands",
            description="Configure the bot for your server",
            color=discord.Color.gold(),
            fields=[
                ("Channel Setup",
                 "`/set_channel` - Configure bot channels\n`/add_channel_type` - Add custom channel type", False),
                ("Role Setup", "`/set_role` - Configure role hierarchy", False),
                ("Games", "`/add_game` - Add supported games", False),
                ("Questions",
                 "`/add_question` - Add application questions\n`/add_conditional_question` - Add follow-up question",
                 False),
                ("Messages",
                 "`/set_welcome_message` - Set welcome channel message\n`/set_rules_message` - Set rules channel message\n`/update_welcome_message` - Update existing welcome\n`/update_rules_message` - Update existing rules",
                 False),
                ("Config", "`/set_welcome` - Set welcome announcement template", False),
                ("View Config", "`/view_config` - View current configuration", False),
                ("Health", "`/health` - Check bot status", False),
            ]
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_channel", description="Configure a bot channel")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channel_type="Type of channel (announcements, moderator_queue, welcome, rules)",
        channel="The channel to use"
    )
    async def set_channel(
            self,
            interaction: discord.Interaction,
            channel_type: str,
            channel: discord.TextChannel
    ):
        """Set a configured channel"""
        if not await self._check_admin(interaction):
            return

        valid_types = ["announcements", "moderator_queue", "welcome", "rules"]
        if channel_type not in valid_types:
            await interaction.response.send_message(
                f"❌ Invalid channel type. Valid types: {', '.join(valid_types)}",
                ephemeral=True
            )
            return

        success = await set_channel(interaction.guild.id, channel_type, channel.id)

        if success:
            await interaction.response.send_message(
                f"✅ Set `{channel_type}` channel to {channel.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to set channel. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="set_role", description="Configure a bot role")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        role_tier="Role tier (sovereign, templar, knight, squire, applicant)",
        role="The role to use"
    )
    async def set_role(
            self,
            interaction: discord.Interaction,
            role_tier: str,
            role: discord.Role
    ):
        """Set a configured role"""
        if not await self._check_admin(interaction):
            return

        tier_map = {
            "sovereign": RoleTier.SOVEREIGN,
            "templar": RoleTier.TEMPLAR,
            "knight": RoleTier.KNIGHT,
            "squire": RoleTier.SQUIRE,
            "applicant": RoleTier.APPLICANT,
            # Legacy support
            "admin": RoleTier.SOVEREIGN,
            "moderator": RoleTier.TEMPLAR,
            "member": RoleTier.SQUIRE
        }

        hierarchy_map = {
            RoleTier.SOVEREIGN: 4,
            RoleTier.TEMPLAR: 3,
            RoleTier.KNIGHT: 2,
            RoleTier.SQUIRE: 1,
            RoleTier.APPLICANT: 0
        }

        if role_tier.lower() not in tier_map:
            await interaction.response.send_message(
                f"❌ Invalid role tier. Valid tiers: {', '.join([k for k in tier_map.keys() if k not in ['admin', 'moderator', 'member']])}",
                ephemeral=True
            )
            return

        tier = tier_map[role_tier.lower()]
        hierarchy = hierarchy_map[tier]
        success = await set_role(interaction.guild.id, tier, role.id, hierarchy)

        if success:
            await interaction.response.send_message(
                f"✅ Set `{role_tier}` role to {role.mention}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to set role. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="set_welcome_message", description="Set the welcome channel message")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def set_welcome_message(self, interaction: discord.Interaction):
        """Set welcome message via modal"""
        if not await self._check_admin(interaction):
            return

        modal = WelcomeMessageModal(self.bot)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="set_rules_message", description="Set the rules channel message")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def set_rules_message(self, interaction: discord.Interaction):
        """Set rules message via modal"""
        if not await self._check_admin(interaction):
            return

        modal = RulesMessageModal(self.bot)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="update_welcome_message", description="Update the existing welcome message")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def update_welcome_message(self, interaction: discord.Interaction):
        """Update existing welcome message"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.welcome_message_id:
                await interaction.response.send_message(
                    "❌ No welcome message set. Use `/set_welcome_message` first.",
                    ephemeral=True
                )
                return

            welcome_channel_id = session.query(ChannelRegistry).filter_by(
                guild_id=guild.id,
                channel_type="welcome"
            ).first()

            if not welcome_channel_id:
                await interaction.response.send_message("❌ Welcome channel not configured.", ephemeral=True)
                return

            channel = interaction.guild.get_channel(welcome_channel_id.channel_id)
            if not channel:
                await interaction.response.send_message("❌ Welcome channel not found.", ephemeral=True)
                return

            try:
                message = await channel.fetch_message(config.welcome_message_id)

                embed = discord.Embed(
                    title="✅ Welcome Message Updated",
                    description=f"The welcome message was successfully posted/updated in {channel.mention}",
                    color=discord.Color.green()
                )

                if config.welcome_message_media_url:
                    await message.edit(content=config.welcome_message_content)
                    embed.add_field(name="Media", value=config.welcome_message_media_url, inline=False)
                else:
                    await message.edit(content=config.welcome_message_content)

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.NotFound:
                await interaction.response.send_message(
                    "❌ Welcome message was deleted. Use `/set_welcome_message` to create a new one.",
                    ephemeral=True
                )

    @app_commands.command(name="update_rules_message", description="Update the existing rules message")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def update_rules_message(self, interaction: discord.Interaction):
        """Update existing rules message"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.rules_message_id:
                await interaction.response.send_message(
                    "❌ No rules message set. Use `/set_rules_message` first.",
                    ephemeral=True
                )
                return

            rules_channel_id = session.query(ChannelRegistry).filter_by(
                guild_id=guild.id,
                channel_type="rules"
            ).first()

            if not rules_channel_id:
                await interaction.response.send_message("❌ Rules channel not configured.", ephemeral=True)
                return

            channel = interaction.guild.get_channel(rules_channel_id.channel_id)
            if not channel:
                await interaction.response.send_message("❌ Rules channel not found.", ephemeral=True)
                return

            try:
                message = await channel.fetch_message(config.rules_message_id)

                embed = discord.Embed(
                    title="✅ Rules Message Updated",
                    description=f"The rules message was successfully updated in {channel.mention}",
                    color=discord.Color.green()
                )

                if config.rules_message_media_url:
                    await message.edit(content=config.rules_message_content)
                    embed.add_field(name="Media", value=config.rules_message_media_url, inline=False)
                else:
                    await message.edit(content=config.rules_message_content)

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.NotFound:
                await interaction.response.send_message(
                    "❌ Rules message was deleted. Use `/set_rules_message` to create a new one.",
                    ephemeral=True
                )

    @app_commands.command(name="add_game", description="Add a supported game")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(game_name="Name of the game")
    async def add_game(self, interaction: discord.Interaction, game_name: str):
        """Add a game for character tracking"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            existing = session.query(Game).filter_by(
                guild_id=guild.id,
                name=game_name
            ).first()

            if existing:
                await interaction.response.send_message(
                    f"❌ Game `{game_name}` already exists.",
                    ephemeral=True
                )
                return

            game = Game(
                guild_id=guild.id,
                name=game_name,
                enabled=True
            )
            session.add(game)
            session.commit()

        await interaction.response.send_message(
            f"✅ Added game: **{game_name}**",
            ephemeral=True
        )

    @app_commands.command(name="add_question", description="Add an application question")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def add_question(self, interaction: discord.Interaction):
        """Add a question via modal"""
        if not await self._check_admin(interaction):
            return

        modal = AddQuestionModal()
        await interaction.response.send_modal(modal)

    @app_commands.command(name="add_conditional_question", description="Add a follow-up question based on an answer")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        parent_question_id="ID of the parent question",
        parent_option_text="Text of the option that triggers this question"
    )
    async def add_conditional_question(
            self,
            interaction: discord.Interaction,
            parent_question_id: int,
            parent_option_text: str
    ):
        """Add a conditional question"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            parent_question = session.query(Question).filter_by(
                id=parent_question_id,
                guild_id=guild.id
            ).first()

            if not parent_question:
                await interaction.response.send_message(
                    f"❌ Parent question ID {parent_question_id} not found.",
                    ephemeral=True
                )
                return

            parent_option = session.query(QuestionOption).filter_by(
                question_id=parent_question_id,
                option_text=parent_option_text
            ).first()

            if not parent_option:
                await interaction.response.send_message(
                    f"❌ Option '{parent_option_text}' not found for question ID {parent_question_id}.",
                    ephemeral=True
                )
                return

        modal = AddConditionalQuestionModal(parent_question_id, parent_option.id)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="set_welcome", description="Set welcome announcement template")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(template="Welcome message (use {mention} for user mention)")
    async def set_welcome(self, interaction: discord.Interaction, template: str):
        """Set welcome message template"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config:
                config = Configuration(guild_id=guild.id)
                session.add(config)

            config.welcome_template = template
            session.commit()

        await interaction.response.send_message(
            f"✅ Welcome template updated:\n```{template}```",
            ephemeral=True
        )

    @app_commands.command(name="view_config", description="View current configuration")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def view_config(self, interaction: discord.Interaction):
        """View server configuration"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🛠️ Server Configuration",
                color=discord.Color.gold()
            )

            channels = session.query(ChannelRegistry).filter_by(guild_id=guild.id).all()
            if channels:
                channel_text = "\n".join([
                    f"**{ch.channel_type}**: <#{ch.channel_id}>"
                    for ch in channels
                ])
                embed.add_field(name="Channels", value=channel_text, inline=False)

            roles = session.query(RoleRegistry).filter_by(guild_id=guild.id).all()
            if roles:
                role_text = "\n".join([
                    f"**{role.role_tier.value}**: <@&{role.role_id}> (level {role.hierarchy_level})"
                    for role in roles
                ])
                embed.add_field(name="Roles", value=role_text, inline=False)

            games = session.query(Game).filter_by(guild_id=guild.id, enabled=True).all()
            if games:
                game_text = ", ".join([game.name for game in games])
                embed.add_field(name="Games", value=game_text, inline=False)

            questions = session.query(Question).filter_by(
                guild_id=guild.id,
                active=True,
                parent_question_id=None
            ).count()

            conditional_questions = session.query(Question).filter_by(
                guild_id=guild.id,
                active=True
            ).filter(Question.parent_question_id.isnot(None)).count()

            embed.add_field(
                name="Application Questions",
                value=f"{questions} main, {conditional_questions} conditional",
                inline=True
            )

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if config:
                embed.add_field(
                    name="Welcome Template",
                    value=f"```{config.welcome_template[:100]}```",
                    inline=False
                )

                if config.welcome_message_id:
                    embed.add_field(
                        name="Welcome Message",
                        value=f"Set (ID: {config.welcome_message_id})",
                        inline=True
                    )

                if config.rules_message_id:
                    embed.add_field(
                        name="Rules Message",
                        value=f"Set (ID: {config.rules_message_id})",
                        inline=True
                    )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="health", description="Check bot health status")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def health(self, interaction: discord.Interaction):
        """Health check command"""
        if not await self._check_admin(interaction):
            return

        db_status = "✅ Connected"
        try:
            with db.session_scope() as session:
                session.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"❌ Error: {str(e)[:100]}"

        embed = await create_embed(
            title="🏥 Bot Health Check",
            color=discord.Color.green(),
            fields=[
                ("Bot Status", "✅ Online", True),
                ("Database", db_status, True),
                ("Latency", f"{round(self.bot.latency * 1000)}ms", True),
                ("Guilds", str(len(self.bot.guilds)), True),
                ("Users", str(len(self.bot.users)), True),
            ]
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        from utils.checks import is_admin
        if not await is_admin(interaction):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return False
        return True


class WelcomeMessageModal(discord.ui.Modal):
    """Modal for setting welcome message"""

    def __init__(self, bot):
        super().__init__(title="Set Welcome Message")
        self.bot = bot

        self.content = discord.ui.TextInput(
            label="Message Content",
            placeholder="Enter the welcome message...",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.content)

        self.media_url = discord.ui.TextInput(
            label="Media URL (optional)",
            placeholder="URL to image or video...",
            style=discord.TextStyle.short,
            required=False,
            max_length=500
        )
        self.add_item(self.media_url)

    async def on_submit(self, interaction: discord.Interaction):
        """Post welcome message"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            welcome_channel_id = session.query(ChannelRegistry).filter_by(
                guild_id=guild.id,
                channel_type="welcome"
            ).first()

            if not welcome_channel_id:
                await interaction.response.send_message(
                    "❌ Welcome channel not configured. Use `/set_channel` first.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(welcome_channel_id.channel_id)
            if not channel:
                await interaction.response.send_message("❌ Welcome channel not found.", ephemeral=True)
                return

            try:
                message = await channel.send(content=self.content.value)

                config = session.query(Configuration).filter_by(guild_id=guild.id).first()
                if not config:
                    config = Configuration(guild_id=guild.id)
                    session.add(config)

                config.welcome_message_content = self.content.value
                config.welcome_message_media_url = self.media_url.value if self.media_url.value else None
                config.welcome_message_id = message.id

                session.commit()

                embed = discord.Embed(
                    title="✅ Welcome Message Set",
                    description=f"The welcome message was successfully posted in {channel.mention}",
                    color=discord.Color.green()
                )

                if self.media_url.value:
                    embed.add_field(name="Media URL", value=self.media_url.value, inline=False)
                    embed.set_footer(
                        text="Note: To display media inline, edit the message in Discord and attach the file directly")

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to post in the welcome channel.",
                    ephemeral=True
                )


class RulesMessageModal(discord.ui.Modal):
    """Modal for setting rules message"""

    def __init__(self, bot):
        super().__init__(title="Set Rules Message")
        self.bot = bot

        self.content = discord.ui.TextInput(
            label="Rules Content",
            placeholder="Enter the server rules...",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )
        self.add_item(self.content)

        self.media_url = discord.ui.TextInput(
            label="Media URL (optional)",
            placeholder="URL to image or video...",
            style=discord.TextStyle.short,
            required=False,
            max_length=500
        )
        self.add_item(self.media_url)

    async def on_submit(self, interaction: discord.Interaction):
        """Post rules message"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            rules_channel_id = session.query(ChannelRegistry).filter_by(
                guild_id=guild.id,
                channel_type="rules"
            ).first()

            if not rules_channel_id:
                await interaction.response.send_message(
                    "❌ Rules channel not configured. Use `/set_channel` first.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(rules_channel_id.channel_id)
            if not channel:
                await interaction.response.send_message("❌ Rules channel not found.", ephemeral=True)
                return

            try:
                message = await channel.send(content=self.content.value)

                config = session.query(Configuration).filter_by(guild_id=guild.id).first()
                if not config:
                    config = Configuration(guild_id=guild.id)
                    session.add(config)

                config.rules_message_content = self.content.value
                config.rules_message_media_url = self.media_url.value if self.media_url.value else None
                config.rules_message_id = message.id

                session.commit()

                embed = discord.Embed(
                    title="✅ Rules Message Set",
                    description=f"The rules message was successfully posted in {channel.mention}",
                    color=discord.Color.green()
                )

                if self.media_url.value:
                    embed.add_field(name="Media URL", value=self.media_url.value, inline=False)
                    embed.set_footer(
                        text="Note: To display media inline, edit the message in Discord and attach the file directly")

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to post in the rules channel.",
                    ephemeral=True
                )


class AddQuestionModal(discord.ui.Modal):
    """Modal for adding a question"""

    def __init__(self):
        super().__init__(title="Add Application Question")

        self.question_text = discord.ui.TextInput(
            label="Question Text",
            placeholder="Enter the question...",
            style=discord.TextStyle.long,
            required=True,
            max_length=500
        )
        self.add_item(self.question_text)

        self.question_type = discord.ui.TextInput(
            label="Question Type",
            placeholder="single_choice, multi_choice, short_text, long_text, numeric",
            required=True,
            max_length=50
        )
        self.add_item(self.question_type)

        self.options = discord.ui.TextInput(
            label="Options (comma-separated, for choice types)",
            placeholder="Option 1, Option 2, Option 3",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.options)

    async def on_submit(self, interaction: discord.Interaction):
        """Save question"""
        type_map = {
            "single_choice": QuestionType.SINGLE_CHOICE,
            "multi_choice": QuestionType.MULTI_CHOICE,
            "short_text": QuestionType.SHORT_TEXT,
            "long_text": QuestionType.LONG_TEXT,
            "numeric": QuestionType.NUMERIC
        }

        q_type = self.question_type.value.lower().strip()
        if q_type not in type_map:
            await interaction.response.send_message(
                f"❌ Invalid question type. Valid types: {', '.join(type_map.keys())}",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            max_order = session.query(Question).filter_by(
                guild_id=guild.id
            ).count()

            question = Question(
                guild_id=guild.id,
                question_text=self.question_text.value,
                question_type=type_map[q_type],
                order=max_order + 1,
                required=True,
                active=True
            )
            session.add(question)
            session.flush()

            question_id = question.id

            if self.options.value and q_type in ["single_choice", "multi_choice"]:
                options = [opt.strip() for opt in self.options.value.split(',') if opt.strip()]
                for idx, opt_text in enumerate(options):
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=opt_text,
                        order=idx + 1,
                        immediate_reject=False
                    )
                    session.add(option)

            session.commit()

        await interaction.response.send_message(
            f"✅ Question added successfully! (ID: {question_id}, Order: {max_order + 1})",
            ephemeral=True
        )


class AddConditionalQuestionModal(discord.ui.Modal):
    """Modal for adding a conditional question"""

    def __init__(self, parent_question_id: int, parent_option_id: int):
        super().__init__(title="Add Conditional Question")
        self.parent_question_id = parent_question_id
        self.parent_option_id = parent_option_id

        self.question_text = discord.ui.TextInput(
            label="Question Text",
            placeholder="Enter the follow-up question...",
            style=discord.TextStyle.long,
            required=True,
            max_length=500
        )
        self.add_item(self.question_text)

        self.question_type = discord.ui.TextInput(
            label="Question Type",
            placeholder="single_choice, multi_choice, short_text, long_text, numeric",
            required=True,
            max_length=50
        )
        self.add_item(self.question_type)

        self.options = discord.ui.TextInput(
            label="Options (comma-separated, for choice types)",
            placeholder="Option 1, Option 2, Option 3",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.options)

    async def on_submit(self, interaction: discord.Interaction):
        """Save conditional question"""
        type_map = {
            "single_choice": QuestionType.SINGLE_CHOICE,
            "multi_choice": QuestionType.MULTI_CHOICE,
            "short_text": QuestionType.SHORT_TEXT,
            "long_text": QuestionType.LONG_TEXT,
            "numeric": QuestionType.NUMERIC
        }

        q_type = self.question_type.value.lower().strip()
        if q_type not in type_map:
            await interaction.response.send_message(
                f"❌ Invalid question type. Valid types: {', '.join(type_map.keys())}",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            max_order = session.query(Question).filter_by(guild_id=guild.id).count()

            question = Question(
                guild_id=guild.id,
                question_text=self.question_text.value,
                question_type=type_map[q_type],
                order=max_order + 1,
                required=True,
                active=True,
                parent_question_id=self.parent_question_id,
                parent_option_id=self.parent_option_id
            )
            session.add(question)
            session.flush()

            question_id = question.id

            if self.options.value and q_type in ["single_choice", "multi_choice"]:
                options = [opt.strip() for opt in self.options.value.split(',') if opt.strip()]
                for idx, opt_text in enumerate(options):
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=opt_text,
                        order=idx + 1,
                        immediate_reject=False
                    )
                    session.add(option)

            session.commit()

        await interaction.response.send_message(
            f"✅ Conditional question added successfully! (ID: {question_id})\nWill appear when parent question's specific option is selected.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))