"""
Enhanced character profiles cog for the Guild Management Bot - MO2 focused
"""
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_

from database import User, Character, get_session, get_character_statistics
from utils.permissions import PermissionChecker
from views.profiles import CharacterManagerView, CharacterStatsView, AdminCharacterBrowserView


class ProfilesCog(commands.Cog):
    """Enhanced character profile management with MO2 integration."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="characters", description="Manage your character profiles")
    async def characters_command(self, interaction: discord.Interaction):
        """Manage user's character profiles."""
        view = CharacterManagerView(interaction.user.id)
        await view.show_characters(interaction)

    @app_commands.command(name="main_character", description="View your main character")
    async def main_character_command(self, interaction: discord.Interaction):
        """Display user's main character."""
        async with get_session() as session:
            # Get user
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == interaction.user.id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                embed = discord.Embed(
                    title="👤 No Characters",
                    description="You haven't created any characters yet!\nUse `/characters` to create one!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            result = await session.execute(
                select(Character).where(
                    and_(
                        Character.user_id == db_user.id,
                        Character.is_main == True
                    )
                )
            )
            main_character = result.scalar_one_or_none()

        if not main_character:
            embed = discord.Embed(
                title="👤 No Main Character",
                description="You don't have a main character set. Use `/characters` to set one!",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title=f"⭐ Your Main Character",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Name",
                value=main_character.name,
                inline=True
            )

            if main_character.race:
                embed.add_field(
                    name="Race",
                    value=main_character.race,
                    inline=True
                )

            if main_character.archetype:
                embed.add_field(
                    name="Archetype",
                    value=main_character.archetype,
                    inline=True
                )

            if main_character.subtype:
                embed.add_field(
                    name="Specialization",
                    value=main_character.subtype,
                    inline=True
                )

            if main_character.professions:
                prof_list = main_character.professions if isinstance(main_character.professions, list) else []
                if prof_list:
                    embed.add_field(
                        name="Professions/Skills",
                        value=", ".join(prof_list),
                        inline=False
                    )

            if main_character.build_url:
                embed.add_field(
                    name="Build Link",
                    value=f"[View Build]({main_character.build_url})",
                    inline=True
                )

            embed.add_field(
                name="Created",
                value=discord.utils.format_dt(main_character.created_at, 'R'),
                inline=True
            )

            if main_character.build_notes:
                embed.add_field(
                    name="Build Notes",
                    value=main_character.build_notes,
                    inline=False
                )

            embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="character_stats", description="View character statistics for the server (Admin only)")
    async def character_stats_command(self, interaction: discord.Interaction):
        """Show character statistics for the server."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view character statistics",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        stats = await get_character_statistics(interaction.guild_id)
        view = CharacterStatsView(stats)
        await view.show_stats(interaction)

    @app_commands.command(name="guild_roster", description="View guild character roster (Admin only)")
    async def guild_roster_command(self, interaction: discord.Interaction):
        """Show the guild's character roster for planning purposes."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view guild roster",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = AdminCharacterBrowserView()
        await view.show_admin_characters(interaction)

    @app_commands.command(name="view_profile", description="View someone's character profile")
    @app_commands.describe(member="The member whose profile you want to view")
    async def view_profile_command(self, interaction: discord.Interaction, member: discord.Member):
        """View another member's character profile."""
        if member.bot:
            embed = discord.Embed(
                title="❌ Bot Account",
                description="Profiles are not available for bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == member.id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                embed = discord.Embed(
                    title="👤 No Profile",
                    description=f"{member.mention} hasn't created any characters yet.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            result = await session.execute(
                select(Character).where(Character.user_id == db_user.id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            characters = result.scalars().all()

        if not characters:
            embed = discord.Embed(
                title="👤 No Characters",
                description=f"{member.mention} hasn't created any characters yet.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Show profile with main character prominent
        main_char = next((c for c in characters if c.is_main), characters[0])

        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Profile",
            color=discord.Color.blue()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        # Main character section
        main_char_text = f"**{main_char.name}**"
        if main_char.race:
            main_char_text += f" ({main_char.race})"
        if main_char.archetype:
            main_char_text += f" - {main_char.archetype}"
        if main_char.subtype:
            main_char_text += f" ({main_char.subtype})"

        embed.add_field(
            name="⭐ Main Character",
            value=main_char_text,
            inline=False
        )

        if main_char.professions:
            prof_list = main_char.professions if isinstance(main_char.professions, list) else []
            if prof_list:
                embed.add_field(
                    name="🛠️ Main Professions",
                    value=", ".join(prof_list[:5]) + ("..." if len(prof_list) > 5 else ""),
                    inline=True
                )

        if main_char.build_url:
            embed.add_field(
                name="🔗 Build Link",
                value=f"[View Build]({main_char.build_url})",
                inline=True
            )

        # Other characters
        other_chars = [c for c in characters if not c.is_main]
        if other_chars:
            other_char_names = []
            for char in other_chars[:5]:  # Show up to 5 alts
                char_text = char.name
                if char.race:
                    char_text += f" ({char.race})"
                other_char_names.append(char_text)

            if len(other_chars) > 5:
                other_char_names.append(f"... and {len(other_chars) - 5} more")

            embed.add_field(
                name="🎭 Other Characters",
                value="\n".join(other_char_names),
                inline=False
            )

        # Summary stats
        embed.add_field(
            name="📊 Summary",
            value=f"**Total Characters:** {len(characters)}",
            inline=True
        )

        if db_user.timezone:
            embed.add_field(
                name="🌍 Timezone",
                value=db_user.timezone,
                inline=True
            )

        embed.set_footer(text=f"Profile created {discord.utils.format_dt(db_user.created_at, 'R')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="admin_manage_profile", description="Manage a member's profile (Admin only)")
    @app_commands.describe(member="The member whose profile to manage")
    async def admin_manage_profile_command(self, interaction: discord.Interaction, member: discord.Member):
        """Admin command to manage member profiles."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage member profiles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if member.bot:
            embed = discord.Embed(
                title="❌ Bot Account",
                description="Profiles are not available for bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = AdminCharacterBrowserView(member)
        await view.show_admin_characters(interaction)

    @app_commands.command(name="find_characters", description="Find characters by race/archetype (Admin only)")
    @app_commands.describe(
        race="Filter by character race",
        archetype="Filter by character archetype"
    )
    async def find_characters_command(self, interaction: discord.Interaction,
                                    race: Optional[str] = None,
                                    archetype: Optional[str] = None):
        """Find characters matching specific criteria."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "search characters",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            query = select(Character).where(Character.guild_id == interaction.guild_id)

            filters = []
            if race:
                query = query.where(Character.race.ilike(f"%{race}%"))
                filters.append(f"Race: {race}")

            if archetype:
                query = query.where(Character.archetype.ilike(f"%{archetype}%"))
                filters.append(f"Archetype: {archetype}")

            query = query.order_by(Character.is_main.desc(), Character.name)
            result = await session.execute(query)
            characters = result.scalars().all()

        embed = discord.Embed(
            title="🔍 Character Search Results",
            color=discord.Color.blue()
        )

        if filters:
            embed.description = f"**Filters:** {', '.join(filters)}"

        if not characters:
            embed.add_field(
                name="No Results",
                value="No characters found matching the criteria.",
                inline=False
            )
        else:
            char_list = []
            for char in characters[:20]:  # Limit to 20 results
                # Get the owner
                char_user = await session.get(User, char.user_id)
                if char_user:
                    member = interaction.guild.get_member(char_user.user_id)
                    owner_name = member.display_name if member else "Unknown"
                else:
                    owner_name = "Unknown"

                main_indicator = "⭐ " if char.is_main else ""
                race_text = f" ({char.race})" if char.race else ""
                archetype_text = f" - {char.archetype}" if char.archetype else ""

                char_list.append(f"{main_indicator}**{char.name}**{race_text}{archetype_text} - *{owner_name}*")

            embed.add_field(
                name=f"Found {len(characters)} character(s)",
                value="\n".join(char_list),
                inline=False
            )

            if len(characters) > 20:
                embed.add_field(
                    name="Note",
                    value=f"Showing first 20 of {len(characters)} results.",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ProfilesCog(bot))