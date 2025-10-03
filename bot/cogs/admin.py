# File: cogs/admin.py
# Location: /bot/cogs/admin.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

from sqlalchemy import text

from models import (
    Guild, ChannelRegistry, RoleRegistry, Question, QuestionOption,
    Game, Configuration, RoleTier, QuestionType
)
from database import db
from utils.helpers import create_embed, set_channel, set_role
from utils.checks import require_admin

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Administrative commands for bot configuration"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin_help", description="View admin commands")
    @app_commands.guild_only()
    async def admin_help(self, interaction: discord.Interaction):
        """Show admin help"""
        if not await self._check_admin(interaction):
            return

        embed = await create_embed(
            title="🛠️ Admin Commands",
            description="Configure the bot for your server",
            color=discord.Color.gold(),
            fields=[
                ("Channel Setup", "`/set_channel` - Configure bot channels", False),
                ("Role Setup", "`/set_role` - Configure role hierarchy", False),
                ("Games", "`/add_game` - Add supported games", False),
                ("Questions", "`/add_question` - Add application questions", False),
                ("Config", "`/set_welcome` - Set welcome message template", False),
                ("View Config", "`/view_config` - View current configuration", False),
                ("Health", "`/health` - Check bot status", False),
            ]
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_channel", description="Configure a bot channel")
    @app_commands.guild_only()
    @app_commands.describe(
        channel_type="Type of channel (announcements, moderator_queue, welcome)",
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

        # Validate channel type
        valid_types = ["announcements", "moderator_queue", "welcome"]
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
    @app_commands.describe(
        role_tier="Role tier (admin, moderator, member, applicant)",
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

        # Convert to RoleTier enum
        tier_map = {
            "admin": RoleTier.ADMIN,
            "moderator": RoleTier.MODERATOR,
            "member": RoleTier.MEMBER,
            "applicant": RoleTier.APPLICANT
        }

        # Built-in hierarchy (admin > moderator > member > applicant)
        hierarchy_map = {
            RoleTier.ADMIN: 3,
            RoleTier.MODERATOR: 2,
            RoleTier.MEMBER: 1,
            RoleTier.APPLICANT: 0
        }

        if role_tier.lower() not in tier_map:
            await interaction.response.send_message(
                f"❌ Invalid role tier. Valid tiers: {', '.join(tier_map.keys())}",
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

    @app_commands.command(name="add_game", description="Add a supported game")
    @app_commands.guild_only()
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

            # Check if game already exists
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
    async def add_question(self, interaction: discord.Interaction):
        """Add a question via modal"""
        if not await self._check_admin(interaction):
            return

        modal = AddQuestionModal()
        await interaction.response.send_modal(modal)

    @app_commands.command(name="set_welcome", description="Set welcome announcement template")
    @app_commands.guild_only()
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

            # Channels
            channels = session.query(ChannelRegistry).filter_by(guild_id=guild.id).all()
            if channels:
                channel_text = "\n".join([
                    f"**{ch.channel_type}**: <#{ch.channel_id}>"
                    for ch in channels
                ])
                embed.add_field(name="Channels", value=channel_text, inline=False)

            # Roles
            roles = session.query(RoleRegistry).filter_by(guild_id=guild.id).all()
            if roles:
                role_text = "\n".join([
                    f"**{role.role_tier.value}**: <@&{role.role_id}> (level {role.hierarchy_level})"
                    for role in roles
                ])
                embed.add_field(name="Roles", value=role_text, inline=False)

            # Games
            games = session.query(Game).filter_by(guild_id=guild.id, enabled=True).all()
            if games:
                game_text = ", ".join([game.name for game in games])
                embed.add_field(name="Games", value=game_text, inline=False)

            # Questions
            questions = session.query(Question).filter_by(
                guild_id=guild.id,
                active=True,
                parent_question_id=None
            ).count()
            embed.add_field(name="Application Questions", value=str(questions), inline=True)

            # Config
            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if config:
                embed.add_field(
                    name="Welcome Template",
                    value=f"```{config.welcome_template[:100]}```",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="health", description="Check bot health status")
    @app_commands.guild_only()
    async def health(self, interaction: discord.Interaction):
        """Health check command"""
        if not await self._check_admin(interaction):
            return

        # Test database connection
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
        # Validate question type
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

            # Get next order number
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

            # Add options if provided
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
            f"✅ Question added successfully! (Order: {max_order + 1})",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))