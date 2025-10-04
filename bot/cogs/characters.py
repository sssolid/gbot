# File: cogs/characters.py
# Location: /bot/cogs/characters.py

import discord
from discord.ext import commands
from discord import app_commands
import json
import logging

from models import Guild, Member, Game, Character, ApplicationStatus
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class CharactersCog(commands.Cog):
    """Handles character and game profile management for approved members"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="character", description="Manage your game characters")
    @app_commands.guild_only()
    async def character(self, interaction: discord.Interaction):
        """Character management menu - available to everyone"""
        if not await self._check_approved(interaction):
            return

        embed = await create_embed(
            title="Character Management",
            description=(
                "Manage your game characters:\n\n"
                "`/character_add` - Add a new character\n"
                "`/character_list` - View your characters\n"
                "`/character_remove` - Remove a character"
            ),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="character_add", description="Add a new character")
    @app_commands.guild_only()
    async def character_add(self, interaction: discord.Interaction):
        """Add a new character - available to everyone"""
        if not await self._check_approved(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            games = session.query(Game).filter_by(
                guild_id=guild.id,
                enabled=True
            ).all()

            if not games:
                await interaction.response.send_message(
                    "❌ No games are configured for this server.",
                    ephemeral=True
                )
                return

            if len(games) == 1:
                modal = CharacterModal(games[0].id, games[0].name)
                await interaction.response.send_modal(modal)
            else:
                view = GameSelectView(games)
                await interaction.response.send_message(
                    "Select a game for your character:",
                    view=view,
                    ephemeral=True
                )

    @app_commands.command(name="character_list", description="View your characters")
    @app_commands.guild_only()
    async def character_list(self, interaction: discord.Interaction):
        """List user's characters - available to everyone"""
        if not await self._check_approved(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            member = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=interaction.user.id
            ).first()

            if not member:
                await interaction.response.send_message(
                    "❌ Member record not found.",
                    ephemeral=True
                )
                return

            characters = session.query(Character).filter_by(
                member_id=member.id
            ).all()

            if not characters:
                await interaction.response.send_message(
                    "📭 You don't have any characters yet. Use `/character_add` to add one!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="Your Characters",
                description=f"You have **{len(characters)}** character(s)",
                color=discord.Color.blue()
            )

            for char in characters:
                game = char.game

                roles = json.loads(char.roles) if char.roles else []
                professions = json.loads(char.professions) if char.professions else []

                details = []
                if char.race:
                    details.append(f"**Race:** {char.race}")
                if roles:
                    details.append(f"**Roles:** {', '.join(roles)}")
                if professions:
                    details.append(f"**Professions:** {', '.join(professions)}")
                if char.notes:
                    details.append(f"**Notes:** {char.notes[:100]}")

                embed.add_field(
                    name=f"{char.name} ({game.name})",
                    value="\n".join(details) if details else "No additional details",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="character_remove", description="Remove a character")
    @app_commands.guild_only()
    async def character_remove(self, interaction: discord.Interaction):
        """Remove a character - available to everyone"""
        if not await self._check_approved(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return

            member = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=interaction.user.id
            ).first()

            if not member:
                await interaction.response.send_message(
                    "❌ Member record not found.",
                    ephemeral=True
                )
                return

            characters = session.query(Character).filter_by(
                member_id=member.id
            ).all()

            if not characters:
                await interaction.response.send_message(
                    "📭 You don't have any characters to remove.",
                    ephemeral=True
                )
                return

            view = CharacterRemoveView(characters)
            await interaction.response.send_message(
                "Select a character to remove:",
                view=view,
                ephemeral=True
            )

    async def _check_approved(self, interaction: discord.Interaction) -> bool:
        """Check if user is an approved member"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message(
                    "❌ Server not configured.",
                    ephemeral=True
                )
                return False

            member = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=interaction.user.id
            ).first()

            if not member or member.status != ApplicationStatus.APPROVED:
                await interaction.response.send_message(
                    "❌ You must be an approved member to use this command.",
                    ephemeral=True
                )
                return False

        return True


class GameSelectView(discord.ui.View):
    """View for selecting a game"""

    def __init__(self, games):
        super().__init__(timeout=180)
        self.games = {str(game.id): game for game in games}

        options = [
            discord.SelectOption(
                label=game.name,
                value=str(game.id)
            )
            for game in games
        ]

        select = discord.ui.Select(
            placeholder="Choose a game...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        game_id = int(interaction.data['values'][0])
        game = self.games[str(game_id)]

        modal = CharacterModal(game_id, game.name)
        await interaction.response.send_modal(modal)


class CharacterModal(discord.ui.Modal):
    """Modal for adding a character"""

    def __init__(self, game_id: int, game_name: str):
        super().__init__(title=f"Add Character - {game_name}")
        self.game_id = game_id
        self.game_name = game_name

        self.char_name = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter character name...",
            required=True,
            max_length=100
        )
        self.add_item(self.char_name)

        if "Mortal Online" in game_name or game_name == "MO2":
            self.race = discord.ui.TextInput(
                label="Race",
                placeholder="e.g., Human, Thursar, Alvarin...",
                required=False,
                max_length=50
            )
            self.add_item(self.race)

            self.roles = discord.ui.TextInput(
                label="Roles (comma-separated)",
                placeholder="e.g., Fighter, Crafter, Tamer...",
                required=False,
                max_length=200
            )
            self.add_item(self.roles)

            self.professions = discord.ui.TextInput(
                label="Professions (comma-separated)",
                placeholder="e.g., Blacksmith, Miner, Archer...",
                required=False,
                max_length=200
            )
            self.add_item(self.professions)

        self.notes = discord.ui.TextInput(
            label="Notes (optional)",
            placeholder="Additional information...",
            style=discord.TextStyle.long,
            required=False,
            max_length=500
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        """Save character"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            member = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=interaction.user.id
            ).first()

            roles_list = []
            professions_list = []

            if hasattr(self, 'roles') and self.roles.value:
                roles_list = [r.strip() for r in self.roles.value.split(',') if r.strip()]

            if hasattr(self, 'professions') and self.professions.value:
                professions_list = [p.strip() for p in self.professions.value.split(',') if p.strip()]

            character = Character(
                member_id=member.id,
                game_id=self.game_id,
                name=self.char_name.value,
                race=self.race.value if hasattr(self, 'race') and self.race.value else None,
                roles=json.dumps(roles_list) if roles_list else None,
                professions=json.dumps(professions_list) if professions_list else None,
                notes=self.notes.value if self.notes.value else None
            )

            session.add(character)
            session.commit()

        embed = await create_embed(
            title="✅ Character Added",
            description=f"Successfully added **{self.char_name.value}** to {self.game_name}!",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterRemoveView(discord.ui.View):
    """View for removing a character"""

    def __init__(self, characters):
        super().__init__(timeout=180)
        self.characters = {str(char.id): char for char in characters}

        options = [
            discord.SelectOption(
                label=f"{char.name} ({char.game.name})",
                value=str(char.id),
                description=char.race[:100] if char.race else "No details"
            )
            for char in characters[:25]
        ]

        select = discord.ui.Select(
            placeholder="Choose a character to remove...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        char_id = int(interaction.data['values'][0])
        character = self.characters[str(char_id)]

        view = ConfirmRemoveView(char_id, character.name)
        await interaction.response.send_message(
            f"Are you sure you want to remove **{character.name}**?",
            view=view,
            ephemeral=True
        )


class ConfirmRemoveView(discord.ui.View):
    """Confirmation for character removal"""

    def __init__(self, char_id: int, char_name: str):
        super().__init__(timeout=60)
        self.char_id = char_id
        self.char_name = char_name

    @discord.ui.button(label="Confirm Remove", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        with db.session_scope() as session:
            character = session.query(Character).filter_by(id=self.char_id).first()
            if character:
                session.delete(character)
                session.commit()

        embed = await create_embed(
            title="✅ Character Removed",
            description=f"Successfully removed **{self.char_name}**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(CharactersCog(bot))