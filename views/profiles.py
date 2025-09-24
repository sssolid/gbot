"""
Character profile management views for the Guild Management Bot - FIXED VERSION
"""
from typing import List, Optional
from datetime import datetime, timezone

import discord
from sqlalchemy import select, and_, update, delete, func
from discord.ext import commands

from database import Character, User, get_session
from utils.permissions import PermissionChecker


class CharacterManagerView(discord.ui.View):
    """Main character profile management interface."""

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.characters: List[Character] = []
        self.current_page = 0

    async def show_character_manager(self, interaction: discord.Interaction):
        """Show character management interface."""
        await self.load_characters(interaction.guild_id)
        embed = self._create_characters_embed(interaction)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_characters(self, guild_id: int):
        """Load user's characters from database."""
        async with get_session() as session:
            result = await session.execute(
                select(Character)
                .where(
                    and_(
                        Character.user_id == self.user_id,
                        Character.guild_id == guild_id,
                        Character.is_active == True
                    )
                )
                .order_by(Character.is_main.desc(), Character.created_at.asc())
            )
            self.characters = result.scalars().all()

    def _create_characters_embed(self, interaction: discord.Interaction):
        """Create embed showing characters."""
        user = interaction.guild.get_member(self.user_id)
        user_name = user.display_name if user else f"Unknown User ({self.user_id})"

        embed = discord.Embed(
            title=f"👤 Character Profiles - {user_name}",
            description="Manage your character profiles",
            color=discord.Color.blue()
        )

        if not self.characters:
            embed.add_field(
                name="No Characters",
                value="You don't have any character profiles yet. Click 'Create Character' to make your first one!",
                inline=False
            )
            return embed

        for i, character in enumerate(self.characters[:10], 1):
            main_indicator = "⭐ " if character.is_main else ""

            embed.add_field(
                name=f"{main_indicator}{character.name}",
                value=(
                    f"**Archetype:** {character.archetype or 'Not set'}\n"
                    f"**Build Notes:** {(character.build_notes or 'None')[:100]}{'...' if character.build_notes and len(character.build_notes) > 100 else ''}\n"
                    f"**Created:** {discord.utils.format_dt(character.created_at, 'R')}"
                ),
                inline=True
            )

        embed.set_footer(text=f"Showing {len(self.characters)} character(s)")

        return embed

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.primary, emoji="➕") # type: ignore[arg-type]
    async def create_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a new character."""
        # Check character limit
        if len(self.characters) >= 10:
            embed = discord.Embed(
                title="❌ Character Limit",
                description="You can have a maximum of 10 characters per server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = CharacterCreationModal(self.user_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Character", style=discord.ButtonStyle.secondary, emoji="✏️") # type: ignore[arg-type]
    async def edit_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit an existing character."""
        if not self.characters:
            await interaction.response.send_message("No characters to edit.", ephemeral=True)
            return

        # Create select menu with characters
        options = [
            discord.SelectOption(
                label=f"{'⭐ ' if char.is_main else ''}{char.name}",
                value=str(char.id),
                description=f"{char.archetype or 'No archetype'}"[:100]
            )
            for char in self.characters[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Choose a character to edit...",
            options=options
        )
        select.callback = self._handle_character_edit

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select a character to edit:", view=view, ephemeral=True)

    async def _handle_character_edit(self, interaction: discord.Interaction):
        """Handle character edit selection."""
        character_id = int(interaction.data['values'][0])

        # Get character
        async with get_session() as session:
            result = await session.execute(
                select(Character).where(Character.id == character_id)
            )
            character = result.scalar_one_or_none()

            if not character:
                await interaction.response.send_message("Character not found.", ephemeral=True)
                return

        modal = CharacterEditModal(character)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Main", style=discord.ButtonStyle.secondary, emoji="⭐") # type: ignore[arg-type]
    async def set_main_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set a character as main."""
        if not self.characters:
            await interaction.response.send_message("No characters available.", ephemeral=True)
            return

        # Create select menu with characters
        options = [
            discord.SelectOption(
                label=f"{'⭐ ' if char.is_main else ''}{char.name}",
                value=str(char.id),
                description="Set as main character"
            )
            for char in self.characters[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Choose main character...",
            options=options
        )
        select.callback = self._handle_set_main

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select your main character:", view=view, ephemeral=True)

    async def _handle_set_main(self, interaction: discord.Interaction):
        """Handle setting main character."""
        try:
            character_id = int(interaction.data['values'][0])

            async with get_session() as session:
                # Remove main status from all characters
                await session.execute(
                    update(Character)
                    .where(
                        and_(
                            Character.user_id == self.user_id,
                            Character.guild_id == interaction.guild_id
                        )
                    )
                    .values(is_main=False)
                )

                # Set new main character
                await session.execute(
                    update(Character)
                    .where(Character.id == character_id)
                    .values(is_main=True)
                )

                # Update user's main_character_id
                await session.execute(
                    update(User)
                    .where(
                        and_(
                            User.id == self.user_id,
                            User.guild_id == interaction.guild_id
                        )
                    )
                    .values(main_character_id=character_id)
                )

                await session.commit()

                # Get character name for response
                result = await session.execute(
                    select(Character.name).where(Character.id == character_id)
                )
                character_name = result.scalar_one()

            embed = discord.Embed(
                title="⭐ Main Character Set",
                description=f"**{character_name}** is now your main character!",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (ValueError, IndexError, discord.HTTPException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to set main character: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Delete Character", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def delete_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete a character."""
        if not self.characters:
            await interaction.response.send_message("No characters to delete.", ephemeral=True)
            return

        # Create select menu with characters
        options = [
            discord.SelectOption(
                label=f"{'⭐ ' if char.is_main else ''}{char.name}",
                value=str(char.id),
                description="Delete this character permanently"
            )
            for char in self.characters[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Choose a character to delete...",
            options=options
        )
        select.callback = self._handle_character_delete

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        embed = discord.Embed(
            title="⚠️ Delete Character",
            description="**Warning:** This action cannot be undone!",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _handle_character_delete(self, interaction: discord.Interaction):
        """Handle character deletion."""
        try:
            character_id = int(interaction.data['values'][0])

            async with get_session() as session:
                # Get character info before deletion
                result = await session.execute(
                    select(Character).where(Character.id == character_id)
                )
                character = result.scalar_one_or_none()

                if not character:
                    await interaction.response.send_message("Character not found.", ephemeral=True)
                    return

                # Soft delete by setting is_active to False
                await session.execute(
                    update(Character)
                    .where(Character.id == character_id)
                    .values(is_active=False)
                )

                # If this was main character, clear main_character_id
                if character.is_main:
                    await session.execute(
                        update(User)
                        .where(
                            and_(
                                User.id == self.user_id,
                                User.guild_id == interaction.guild_id
                            )
                        )
                        .values(main_character_id=None)
                    )

                await session.commit()

            embed = discord.Embed(
                title="🗑️ Character Deleted",
                description=f"**{character.name}** has been deleted.",
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (ValueError, IndexError, discord.HTTPException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to delete character: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄") # type: ignore[arg-type]
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the character list."""
        await self.load_characters(interaction.guild_id)
        embed = self._create_characters_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)


class CharacterCreationModal(discord.ui.Modal):
    """Modal for creating new characters."""

    def __init__(self, user_id: int):
        super().__init__(title="Create Character")
        self.user_id = user_id

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter character name",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)

        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            placeholder="e.g., Tank, DPS, Healer, Mage, etc.",
            required=False,
            max_length=100
        )
        self.add_item(self.archetype_input)

        self.build_notes_input = discord.ui.TextInput(
            label="Build Notes",
            placeholder="Describe your character build, stats, or playstyle...",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=False,
            max_length=1000
        )
        self.add_item(self.build_notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle character creation."""
        try:
            name = self.name_input.value.strip()
            archetype = self.archetype_input.value.strip() or None
            build_notes = self.build_notes_input.value.strip() or None

            # Check if name is unique for this user in this guild
            async with get_session() as session:
                existing = await session.execute(
                    select(Character).where(
                        and_(
                            Character.user_id == self.user_id,
                            Character.guild_id == interaction.guild_id,
                            Character.name.ilike(name),  # Case-insensitive
                            Character.is_active == True
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    embed = discord.Embed(
                        title="❌ Name Taken",
                        description=f"You already have a character named **{name}**. Please choose a different name.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Check if this will be the first character (auto-main)
                count_result = await session.execute(
                    select(func.count(Character.id)).where(
                        and_(
                            Character.user_id == self.user_id,
                            Character.guild_id == interaction.guild_id,
                            Character.is_active == True
                        )
                    )
                )
                is_first = count_result.scalar() == 0

                # Create character
                character = Character(
                    user_id=self.user_id,
                    guild_id=interaction.guild_id,
                    name=name,
                    archetype=archetype,
                    build_notes=build_notes,
                    is_main=is_first,  # First character is automatically main
                    is_active=True,
                    created_at=datetime.now(timezone.utc)
                )
                session.add(character)
                await session.commit()
                await session.refresh(character)

                # If this is the main character, update user record
                if is_first:
                    # Ensure user record exists
                    user_result = await session.execute(
                        select(User).where(
                            and_(
                                User.id == self.user_id,
                                User.guild_id == interaction.guild_id
                            )
                        )
                    )
                    user = user_result.scalar_one_or_none()

                    if not user:
                        # Create user record
                        user = User(
                            id=self.user_id,
                            guild_id=interaction.guild_id,
                            main_character_id=character.id,
                            is_active=True,
                            created_at=datetime.now(timezone.utc)
                        )
                        session.add(user)
                    else:
                        # Update existing user record
                        await session.execute(
                            update(User)
                            .where(User.id == user.id)
                            .values(main_character_id=character.id)
                        )

                    await session.commit()

            # Success response
            embed = discord.Embed(
                title="✅ Character Created",
                description=f"**{name}** has been created successfully!",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Character Details",
                value=(
                    f"**Name:** {name}\n"
                    f"**Archetype:** {archetype or 'Not set'}\n"
                    f"**Main Character:** {'Yes' if is_first else 'No'}"
                ),
                inline=False
            )

            if build_notes:
                embed.add_field(
                    name="Build Notes",
                    value=build_notes[:500] + ("..." if len(build_notes) > 500 else ""),
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create character: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterEditModal(discord.ui.Modal):
    """Modal for editing existing characters."""

    def __init__(self, character: Character):
        super().__init__(title=f"Edit {character.name}")
        self.character = character

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter character name",
            default=character.name,
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)

        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            placeholder="e.g., Tank, DPS, Healer, Mage, etc.",
            default=character.archetype or "",
            required=False,
            max_length=100
        )
        self.add_item(self.archetype_input)

        self.build_notes_input = discord.ui.TextInput(
            label="Build Notes",
            placeholder="Describe your character build, stats, or playstyle...",
            default=character.build_notes or "",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=False,
            max_length=1000
        )
        self.add_item(self.build_notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle character edit."""
        try:
            name = self.name_input.value.strip()
            archetype = self.archetype_input.value.strip() or None
            build_notes = self.build_notes_input.value.strip() or None

            # Check if name is unique (excluding current character)
            async with get_session() as session:
                existing = await session.execute(
                    select(Character).where(
                        and_(
                            Character.user_id == self.character.user_id,
                            Character.guild_id == self.character.guild_id,
                            Character.name.ilike(name),  # Case-insensitive
                            Character.id != self.character.id,  # Exclude current character
                            Character.is_active == True
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    embed = discord.Embed(
                        title="❌ Name Taken",
                        description=f"You already have a character named **{name}**. Please choose a different name.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Update character
                await session.execute(
                    update(Character)
                    .where(Character.id == self.character.id)
                    .values(
                        name=name,
                        archetype=archetype,
                        build_notes=build_notes,
                        updated_at=datetime.now(timezone.utc)
                    )
                )
                await session.commit()

            # Success response
            embed = discord.Embed(
                title="✅ Character Updated",
                description=f"**{name}** has been updated successfully!",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Updated Details",
                value=(
                    f"**Name:** {name}\n"
                    f"**Archetype:** {archetype or 'Not set'}"
                ),
                inline=False
            )

            if build_notes:
                embed.add_field(
                    name="Build Notes",
                    value=build_notes[:500] + ("..." if len(build_notes) > 500 else ""),
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to update character: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterViewerView(discord.ui.View):
    """View for displaying character profiles."""

    def __init__(self, target_user_id: int):
        super().__init__(timeout=300)
        self.target_user_id = target_user_id
        self.characters: List[Character] = []
        self.current_character = 0

    async def show_character_profile(self, interaction: discord.Interaction):
        """Show character profile viewer."""
        await self.load_characters(interaction.guild_id)

        if not self.characters:
            user = interaction.guild.get_member(self.target_user_id)
            user_name = user.display_name if user else f"User {self.target_user_id}"

            embed = discord.Embed(
                title=f"👤 {user_name}'s Characters",
                description="This user has no character profiles.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = self._create_character_embed(interaction)

        # Only show navigation if multiple characters
        if len(self.characters) > 1:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def load_characters(self, guild_id: int):
        """Load target user's characters."""
        async with get_session() as session:
            result = await session.execute(
                select(Character)
                .where(
                    and_(
                        Character.user_id == self.target_user_id,
                        Character.guild_id == guild_id,
                        Character.is_active == True
                    )
                )
                .order_by(Character.is_main.desc(), Character.created_at.asc())
            )
            self.characters = result.scalars().all()

    def _create_character_embed(self, interaction: discord.Interaction):
        """Create embed for character display."""
        character = self.characters[self.current_character]
        user = interaction.guild.get_member(self.target_user_id)
        user_name = user.display_name if user else f"User {self.target_user_id}"

        embed = discord.Embed(
            title=f"👤 {user_name}'s Character",
            description=f"**{character.name}**" + (" ⭐" if character.is_main else ""),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Archetype",
            value=character.archetype or "Not specified",
            inline=True
        )

        embed.add_field(
            name="Main Character",
            value="Yes" if character.is_main else "No",
            inline=True
        )

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(character.created_at, 'R'),
            inline=True
        )

        if character.build_notes:
            embed.add_field(
                name="Build Notes",
                value=character.build_notes[:1000] + ("..." if len(character.build_notes) > 1000 else ""),
                inline=False
            )

        if len(self.characters) > 1:
            embed.set_footer(text=f"Character {self.current_character + 1} of {len(self.characters)}")

        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️") # type: ignore[arg-type]
    async def previous_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show previous character."""
        if self.current_character > 0:
            self.current_character -= 1
        else:
            self.current_character = len(self.characters) - 1

        embed = self._create_character_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️") # type: ignore[arg-type]
    async def next_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show next character."""
        if self.current_character < len(self.characters) - 1:
            self.current_character += 1
        else:
            self.current_character = 0

        embed = self._create_character_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)


# FIXED: Added missing ProfileAdminView
class ProfileAdminView(discord.ui.View):
    """Admin interface for managing member profiles."""

    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.users_with_characters: List[int] = []

    async def show_admin_interface(self, interaction: discord.Interaction):
        """Show the profile administration interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage member profiles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.load_users_with_characters(interaction.guild_id)
        embed = self._create_admin_embed(interaction)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_users_with_characters(self, guild_id: int):
        """Load users who have characters."""
        async with get_session() as session:
            result = await session.execute(
                select(Character.user_id)
                .where(
                    and_(
                        Character.guild_id == guild_id,
                        Character.is_active == True
                    )
                )
                .distinct()
            )
            self.users_with_characters = [row[0] for row in result]

    def _create_admin_embed(self, interaction: discord.Interaction):
        """Create admin overview embed."""
        embed = discord.Embed(
            title="👥 Profile Administration",
            description=f"Managing character profiles for {interaction.guild.name}",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="Statistics",
            value=f"**Users with Characters:** {len(self.users_with_characters)}",
            inline=False
        )

        embed.add_field(
            name="Available Actions",
            value=(
                "• **View User Profiles** - Browse member character profiles\n"
                "• **Search Characters** - Find characters by name or archetype\n"
                "• **Manage Characters** - Edit or delete character profiles\n"
                "• **Export Data** - Download character data for backup\n"
                "• **Clean Inactive** - Remove characters from inactive members"
            ),
            inline=False
        )

        return embed

    @discord.ui.button(label="View User Profiles", style=discord.ButtonStyle.primary, emoji="👤") # type: ignore[arg-type]
    async def view_user_profiles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View character profiles by user."""
        if not self.users_with_characters:
            embed = discord.Embed(
                title="📭 No Character Profiles",
                description="No users have created character profiles yet.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Create select menu with users
        options = []
        for user_id in self.users_with_characters[:25]:  # Discord limit
            user = interaction.guild.get_member(user_id)
            if user:
                options.append(discord.SelectOption(
                    label=user.display_name,
                    value=str(user_id),
                    description=f"View {user.display_name}'s character profiles"
                ))

        if not options:
            embed = discord.Embed(
                title="❌ No Active Users",
                description="All users with character profiles have left the server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        select = discord.ui.Select(
            placeholder="Choose a user to view...",
            options=options
        )
        select.callback = self._handle_view_user_profiles

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select a user to view their profiles:", view=view, ephemeral=True)

    async def _handle_view_user_profiles(self, interaction: discord.Interaction):
        """Handle viewing user profiles."""
        user_id = int(interaction.data['values'][0])

        viewer = CharacterViewerView(user_id)
        await viewer.show_character_profile(interaction)

    @discord.ui.button(label="Search Characters", style=discord.ButtonStyle.secondary, emoji="🔍") # type: ignore[arg-type]
    async def search_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Search for characters."""
        modal = CharacterSearchModal()
        modal.admin_view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Character Statistics", style=discord.ButtonStyle.secondary, emoji="📊") # type: ignore[arg-type]
    async def character_statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show character statistics."""
        async with get_session() as session:
            # Total characters
            total_result = await session.execute(
                select(func.count(Character.id))
                .where(
                    and_(
                        Character.guild_id == interaction.guild_id,
                        Character.is_active == True
                    )
                )
            )
            total_characters = total_result.scalar()

            # Characters by archetype
            archetype_result = await session.execute(
                select(Character.archetype, func.count(Character.id))
                .where(
                    and_(
                        Character.guild_id == interaction.guild_id,
                        Character.is_active == True,
                        Character.archetype.isnot(None)
                    )
                )
                .group_by(Character.archetype)
                .order_by(func.count(Character.id).desc())
                .limit(10)
            )
            archetypes = archetype_result.all()

            # Users with multiple characters
            multi_char_result = await session.execute(
                select(func.count(Character.user_id))
                .where(
                    and_(
                        Character.guild_id == interaction.guild_id,
                        Character.is_active == True
                    )
                )
                .group_by(Character.user_id)
                .having(func.count(Character.id) > 1)
            )
            users_with_multiple = len(multi_char_result.all())

        embed = discord.Embed(
            title="📊 Character Statistics",
            description=f"Character profile statistics for {interaction.guild.name}",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Overview",
            value=(
                f"**Total Characters:** {total_characters}\n"
                f"**Users with Characters:** {len(self.users_with_characters)}\n"
                f"**Users with Multiple Characters:** {users_with_multiple}"
            ),
            inline=False
        )

        if archetypes:
            archetype_list = [f"**{arch}:** {count}" for arch, count in archetypes[:5]]
            embed.add_field(
                name="Popular Archetypes",
                value="\n".join(archetype_list),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Clean Inactive", style=discord.ButtonStyle.danger, emoji="🗑️") # type: ignore[arg-type]
    async def clean_inactive_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clean characters from users who left the server."""
        try:
            inactive_users = []
            for user_id in self.users_with_characters:
                member = interaction.guild.get_member(user_id)
                if not member:
                    inactive_users.append(user_id)

            if not inactive_users:
                embed = discord.Embed(
                    title="✅ No Cleanup Needed",
                    description="All character profiles belong to active server members.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Clean up characters from inactive users
            async with get_session() as session:
                result = await session.execute(
                    update(Character)
                    .where(
                        and_(
                            Character.guild_id == interaction.guild_id,
                            Character.user_id.in_(inactive_users),
                            Character.is_active == True
                        )
                    )
                    .values(is_active=False)
                )
                cleaned_count = result.rowcount
                await session.commit()

            embed = discord.Embed(
                title="🗑️ Cleanup Complete",
                description=f"Cleaned up {cleaned_count} character(s) from {len(inactive_users)} inactive user(s).",
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Refresh data
            await self.load_users_with_characters(interaction.guild_id)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to clean inactive characters: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Refresh Data", style=discord.ButtonStyle.secondary, emoji="🔄") # type: ignore[arg-type]
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the admin data."""
        await self.load_users_with_characters(interaction.guild_id)
        embed = self._create_admin_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)


class CharacterSearchModal(discord.ui.Modal):
    """Modal for searching characters."""

    def __init__(self):
        super().__init__(title="Search Characters")
        self.admin_view = None

        self.search_query = discord.ui.TextInput(
            label="Search Query",
            placeholder="Enter character name or archetype to search for",
            required=True,
            max_length=100
        )
        self.add_item(self.search_query)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle character search."""
        try:
            query = self.search_query.value.strip()

            async with get_session() as session:
                # Search by name or archetype
                result = await session.execute(
                    select(Character)
                    .where(
                        and_(
                            Character.guild_id == interaction.guild_id,
                            Character.is_active == True,
                            (
                                Character.name.ilike(f"%{query}%") |
                                Character.archetype.ilike(f"%{query}%")
                            )
                        )
                    )
                    .order_by(Character.name.asc())
                    .limit(25)
                )
                characters = result.scalars().all()

            if not characters:
                embed = discord.Embed(
                    title="🔍 No Results",
                    description=f"No characters found matching **{query}**.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🔍 Search Results: '{query}'",
                description=f"Found {len(characters)} character(s)",
                color=discord.Color.blue()
            )

            for character in characters[:10]:  # Show first 10 results
                user = interaction.guild.get_member(character.user_id)
                user_name = user.display_name if user else f"Unknown ({character.user_id})"

                embed.add_field(
                    name=f"{'⭐ ' if character.is_main else ''}{character.name}",
                    value=(
                        f"**Owner:** {user_name}\n"
                        f"**Archetype:** {character.archetype or 'Not set'}\n"
                        f"**Created:** {discord.utils.format_dt(character.created_at, 'R')}"
                    ),
                    inline=True
                )

            if len(characters) > 10:
                embed.set_footer(text=f"Showing first 10 of {len(characters)} results")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Search Error",
                description=f"Failed to search characters: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)