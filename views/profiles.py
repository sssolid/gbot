"""
Enhanced character profile management views for the Guild Management Bot - MO2 Focused
"""
import discord
from sqlalchemy import select, and_, update, delete, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from database import User, Character, CharacterArchetype, get_session, get_character_statistics
from utils.permissions import PermissionChecker
from utils.constants import MO2_RACES, MO2_ARCHETYPES, MO2_PROFESSIONS


class CharacterManagerView(discord.ui.View):
    """Enhanced character management view with MO2 integration."""

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.characters: List[Character] = []

    async def show_characters(self, interaction: discord.Interaction):
        """Display user's characters with enhanced information."""
        await self.load_characters(interaction.guild_id)

        embed = discord.Embed(
            title="👤 My Characters",
            description="Manage your Mortal Online 2 character profiles",
            color=discord.Color.blue()
        )

        if not self.characters:
            embed.add_field(
                name="No Characters",
                value="You haven't created any characters yet. Click 'Create Character' to get started!\n\n*Build your guild roster with detailed MO2 character information.*",
                inline=False
            )
        else:
            for char in self.characters:
                main_indicator = "⭐ " if char.is_main else ""
                race_text = f" ({char.race})" if char.race else ""
                archetype_text = f" - {char.archetype}" if char.archetype else ""
                subtype_text = f" ({char.subtype})" if char.subtype else ""

                value = f"**{main_indicator}{char.name}**{race_text}{archetype_text}{subtype_text}"

                if char.professions:
                    prof_list = char.professions if isinstance(char.professions, list) else []
                    if prof_list:
                        value += f"\n🛠️ *{', '.join(prof_list[:3])}{'...' if len(prof_list) > 3 else ''}*"

                if char.build_notes:
                    value += f"\n📝 *{char.build_notes[:80]}{'...' if len(char.build_notes) > 80 else ''}*"

                if char.build_url:
                    value += f"\n🔗 [Build Link]({char.build_url})"

                embed.add_field(
                    name=f"Character {len([f for f in embed.fields]) + 1}",
                    value=value,
                    inline=False
                )

        embed.set_footer(text="💡 Tip: Set detailed character info to help with guild organization and planning!")

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_characters(self, guild_id: int):
        """Load user's characters from database."""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == self.user_id,
                        User.guild_id == guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()

            if db_user:
                result = await session.execute(
                    select(Character).where(Character.user_id == db_user.id)
                    .order_by(Character.is_main.desc(), Character.created_at)
                )
                self.characters = result.scalars().all()
            else:
                self.characters = []

    @discord.ui.select(
        placeholder="Select a character to manage...",
        options=[discord.SelectOption(label="No characters", value="none")]
    )
    async def character_select(self, interaction: discord.Interaction, menu: discord.ui.Select):
        """Select a character to manage."""
        if not self.characters:
            await interaction.response.send_message(
                "You don't have any characters to manage.", ephemeral=True
            )
            return

        character_id = int(menu.values[0])
        character = next((c for c in self.characters if c.id == character_id), None)

        if not character:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return

        view = CharacterActionView(character)

        embed = discord.Embed(
            title=f"👤 {character.name}",
            color=discord.Color.blue()
        )

        if character.race:
            embed.add_field(name="Race", value=character.race, inline=True)

        if character.archetype:
            embed.add_field(name="Archetype", value=character.archetype, inline=True)

        if character.subtype:
            embed.add_field(name="Specialization", value=character.subtype, inline=True)

        if character.is_main:
            embed.add_field(name="Status", value="⭐ Main Character", inline=True)

        if character.professions:
            prof_list = character.professions if isinstance(character.professions, list) else []
            if prof_list:
                embed.add_field(
                    name="Professions/Skills",
                    value=", ".join(prof_list),
                    inline=False
                )

        if character.build_url:
            embed.add_field(name="Build Link", value=f"[View Build]({character.build_url})", inline=True)

        if character.build_notes:
            embed.add_field(name="Build Notes", value=character.build_notes, inline=False)

        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(character.created_at, 'F'),
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.primary, emoji="➕")
    async def create_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a new character with enhanced form."""
        modal = EnhancedCharacterCreationModal(self.user_id)
        await interaction.response.send_modal(modal)

    async def on_view_start(self):
        """Update the select menu with current characters."""
        if self.characters:
            options = []
            for char in self.characters[:25]:  # Discord limit
                main_indicator = "⭐ " if char.is_main else ""
                race_text = f" ({char.race})" if char.race else ""
                archetype_text = f" - {char.archetype}" if char.archetype else ""

                options.append(discord.SelectOption(
                    label=f"{main_indicator}{char.name}",
                    description=f"ID: {char.id}{race_text}{archetype_text}",
                    value=str(char.id),
                    emoji="⭐" if char.is_main else "👤"
                ))

            self.character_select.options = options
            self.character_select.placeholder = "Select a character to manage..."
        else:
            self.character_select.options = [discord.SelectOption(label="No characters", value="none")]
            self.character_select.placeholder = "No characters to manage"


class EnhancedCharacterCreationModal(discord.ui.Modal):
    """Enhanced modal for creating MO2 characters."""

    def __init__(self, user_id: int):
        super().__init__(title="Create MO2 Character")
        self.user_id = user_id

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character's name...",
            required=True,
            max_length=100
        )

        self.build_url_input = discord.ui.TextInput(
            label="Build Planner URL (Optional)",
            placeholder="https://www.mortaldata.com/calculator/...",
            required=False,
            max_length=500
        )

        self.notes_input = discord.ui.TextInput(
            label="Build Notes (Optional)",
            placeholder="Describe your character's playstyle, goals, etc.",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )

        self.add_item(self.name_input)
        self.add_item(self.build_url_input)
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle initial character creation, then show detailed form."""
        name = self.name_input.value.strip()
        build_url = self.build_url_input.value.strip() or None
        build_notes = self.notes_input.value.strip() or None

        # Show character details selection view
        view = CharacterDetailsSelectionView(
            self.user_id, name, build_url, build_notes
        )

        embed = discord.Embed(
            title="🎯 Character Details",
            description=f"**Character Name:** {name}\n\nNow let's set up the detailed information for your character:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Next Steps",
            value="• Select character race\n• Choose archetype/class\n• Pick specialization\n• Set professions/skills",
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CharacterDetailsSelectionView(discord.ui.View):
    """Multi-step character details selection."""

    def __init__(self, user_id: int, name: str, build_url: Optional[str], build_notes: Optional[str]):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.name = name
        self.build_url = build_url
        self.build_notes = build_notes
        self.race: Optional[str] = None
        self.archetype: Optional[str] = None
        self.subtype: Optional[str] = None
        self.professions: List[str] = []
        self.step = 1

        self.update_view()

    def update_view(self):
        """Update view based on current step."""
        self.clear_items()

        if self.step == 1:
            # Race selection
            options = []
            for race in MO2_RACES[:25]:  # Discord limit
                options.append(discord.SelectOption(
                    label=race,
                    value=race,
                    emoji="🧬"
                ))

            select = discord.ui.Select(
                placeholder="Select character race...",
                options=options
            )
            select.callback = self.select_race
            self.add_item(select)

        elif self.step == 2:
            # Archetype selection
            options = []
            for archetype_name in MO2_ARCHETYPES.keys():
                options.append(discord.SelectOption(
                    label=archetype_name,
                    value=archetype_name,
                    description=f"Various {archetype_name.lower()} builds",
                    emoji="⚔️" if archetype_name == "Warrior" else "🔮" if archetype_name == "Mage" else "🎯"
                ))

            select = discord.ui.Select(
                placeholder="Select character archetype...",
                options=options
            )
            select.callback = self.select_archetype
            self.add_item(select)

        elif self.step == 3 and self.archetype:
            # Subtype selection
            subtypes = MO2_ARCHETYPES.get(self.archetype, {}).get("subtypes", [])
            if subtypes:
                options = []
                for subtype in subtypes[:25]:  # Discord limit
                    options.append(discord.SelectOption(
                        label=subtype,
                        value=subtype,
                        emoji="🎯"
                    ))

                # Add "Custom/Other" option
                options.append(discord.SelectOption(
                    label="Custom/Other",
                    value="custom",
                    description="Custom build or unlisted specialization",
                    emoji="✨"
                ))

                select = discord.ui.Select(
                    placeholder="Select specialization...",
                    options=options
                )
                select.callback = self.select_subtype
                self.add_item(select)
            else:
                self.step = 4
                self.update_view()
                return

        elif self.step == 4:
            # Profession selection
            options = []
            for profession in MO2_PROFESSIONS[:25]:  # Discord limit
                options.append(discord.SelectOption(
                    label=profession,
                    value=profession,
                    emoji="🛠️"
                ))

            select = discord.ui.Select(
                placeholder="Select professions/skills (multiple allowed)...",
                options=options,
                max_values=min(len(MO2_PROFESSIONS), 25)
            )
            select.callback = self.select_professions
            self.add_item(select)

            # Skip button for professions
            skip_button = discord.ui.Button(
                label="Skip Professions",
                style=discord.ButtonStyle.secondary,
                emoji="⏭️"
            )
            skip_button.callback = self.skip_professions
            self.add_item(skip_button)

        # Add final create button on last step
        if self.step >= 4:
            create_button = discord.ui.Button(
                label="Create Character",
                style=discord.ButtonStyle.success,
                emoji="✅"
            )
            create_button.callback = self.create_character
            self.add_item(create_button)

    async def select_race(self, interaction: discord.Interaction):
        """Handle race selection."""
        self.race = interaction.data['values'][0]
        self.step = 2
        self.update_view()

        embed = discord.Embed(
            title="🎯 Character Details",
            description=f"**Name:** {self.name}\n**Race:** {self.race}\n\nNow select your character's archetype:",
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def select_archetype(self, interaction: discord.Interaction):
        """Handle archetype selection."""
        self.archetype = interaction.data['values'][0]
        self.step = 3
        self.update_view()

        embed = discord.Embed(
            title="🎯 Character Details",
            description=f"**Name:** {self.name}\n**Race:** {self.race}\n**Archetype:** {self.archetype}\n\nChoose a specialization:",
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def select_subtype(self, interaction: discord.Interaction):
        """Handle subtype selection."""
        selected_subtype = interaction.data['values'][0]

        if selected_subtype == "custom":
            modal = CustomSubtypeModal(self)
            await interaction.response.send_modal(modal)
            return

        self.subtype = selected_subtype
        self.step = 4
        self.update_view()

        embed = discord.Embed(
            title="🎯 Character Details",
            description=f"**Name:** {self.name}\n**Race:** {self.race}\n**Archetype:** {self.archetype}\n**Specialization:** {self.subtype}\n\nSelect your main professions/skills:",
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def select_professions(self, interaction: discord.Interaction):
        """Handle profession selection."""
        self.professions = interaction.data['values']

        embed = discord.Embed(
            title="✅ Character Setup Complete",
            description=self.get_character_summary(),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Ready to Create",
            value="Click 'Create Character' to finalize your character!",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def skip_professions(self, interaction: discord.Interaction):
        """Skip profession selection."""
        self.professions = []

        embed = discord.Embed(
            title="✅ Character Setup Complete",
            description=self.get_character_summary(),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Ready to Create",
            value="Click 'Create Character' to finalize your character!",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def create_character(self, interaction: discord.Interaction):
        """Create the character in database."""
        async with get_session() as session:
            # Get or create user
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == self.user_id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                db_user = User(
                    user_id=self.user_id,
                    guild_id=interaction.guild_id
                )
                session.add(db_user)
                await session.flush()  # Get the ID

            # Check if this is the first character (make it main)
            result = await session.execute(
                select(Character).where(Character.user_id == db_user.id)
            )
            existing_chars = result.scalars().all()
            is_main = len(existing_chars) == 0

            # Create character
            character = Character(
                name=self.name,
                race=self.race,
                archetype=self.archetype,
                subtype=self.subtype,
                professions=self.professions if self.professions else None,
                build_url=self.build_url,
                build_notes=self.build_notes,
                is_main=is_main,
                user_id=db_user.id,
                guild_id=interaction.guild_id,  # Add guild_id for character statistics
                created_at=datetime.now(timezone.utc)
            )

            session.add(character)
            await session.commit()

        embed = discord.Embed(
            title="✅ Character Created",
            description=f"Successfully created **{self.name}**!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Character Details",
            value=self.get_character_summary(),
            inline=False
        )

        if is_main:
            embed.add_field(
                name="Main Character",
                value="⭐ This character has been set as your main character since it's your first one.",
                inline=False
            )

        await interaction.response.edit_message(embed=embed, view=None)

    def get_character_summary(self) -> str:
        """Get a formatted summary of character details."""
        summary = f"**Name:** {self.name}"
        if self.race:
            summary += f"\n**Race:** {self.race}"
        if self.archetype:
            summary += f"\n**Archetype:** {self.archetype}"
        if self.subtype:
            summary += f"\n**Specialization:** {self.subtype}"
        if self.professions:
            summary += f"\n**Professions:** {', '.join(self.professions)}"
        if self.build_url:
            summary += f"\n**Build Link:** [View Build]({self.build_url})"
        if self.build_notes:
            summary += f"\n**Notes:** {self.build_notes[:100]}{'...' if len(self.build_notes) > 100 else ''}"

        return summary


class CustomSubtypeModal(discord.ui.Modal):
    """Modal for custom subtype entry."""

    def __init__(self, parent_view: CharacterDetailsSelectionView):
        super().__init__(title="Custom Specialization")
        self.parent_view = parent_view

        self.subtype_input = discord.ui.TextInput(
            label="Custom Specialization",
            placeholder="Enter your custom build/specialization name...",
            required=True,
            max_length=100
        )

        self.add_item(self.subtype_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle custom subtype submission."""
        self.parent_view.subtype = self.subtype_input.value.strip()
        self.parent_view.step = 4
        self.parent_view.update_view()

        embed = discord.Embed(
            title="🎯 Character Details",
            description=f"**Name:** {self.parent_view.name}\n**Race:** {self.parent_view.race}\n**Archetype:** {self.parent_view.archetype}\n**Specialization:** {self.parent_view.subtype}\n\nSelect your main professions/skills:",
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class CharacterActionView(discord.ui.View):
    """Enhanced actions for a specific character."""

    def __init__(self, character: Character):
        super().__init__(timeout=300)
        self.character = character

    @discord.ui.button(label="Set as Main", style=discord.ButtonStyle.primary, emoji="⭐")
    async def set_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set character as main."""
        if self.character.is_main:
            await interaction.response.send_message("This character is already your main character.", ephemeral=True)
            return

        async with get_session() as session:
            # Unset current main
            await session.execute(
                update(Character)
                .where(
                    and_(
                        Character.user_id == self.character.user_id,
                        Character.is_main == True
                    )
                )
                .values(is_main=False, updated_at=datetime.now(timezone.utc))
            )

            # Set new main
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(is_main=True, updated_at=datetime.now(timezone.utc))
            )

            await session.commit()

        embed = discord.Embed(
            title="⭐ Main Character Set",
            description=f"**{self.character.name}** is now your main character!",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit character details."""
        modal = EnhancedCharacterEditModal(self.character)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete character."""
        view = CharacterDeletionView(self.character)

        embed = discord.Embed(
            title="⚠️ Delete Character",
            description=f"Are you sure you want to delete **{self.character.name}**?\n\nThis action cannot be undone.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class EnhancedCharacterEditModal(discord.ui.Modal):
    """Enhanced modal for editing a character."""

    def __init__(self, character: Character):
        super().__init__(title=f"Edit {character.name}")
        self.character = character

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            default=character.name,
            required=True,
            max_length=100
        )

        self.build_url_input = discord.ui.TextInput(
            label="Build Planner URL",
            default=character.build_url or "",
            required=False,
            max_length=500
        )

        self.notes_input = discord.ui.TextInput(
            label="Build Notes",
            default=character.build_notes or "",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )

        self.add_item(self.name_input)
        self.add_item(self.build_url_input)
        self.add_item(self.notes_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle character edit submission."""
        name = self.name_input.value.strip()
        build_url = self.build_url_input.value.strip() or None
        build_notes = self.notes_input.value.strip() or None

        async with get_session() as session:
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(
                    name=name,
                    build_url=build_url,
                    build_notes=build_notes,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await session.commit()

        embed = discord.Embed(
            title="✅ Character Updated",
            description=f"Successfully updated **{name}**!",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterDeletionView(discord.ui.View):
    """Confirmation view for character deletion."""

    def __init__(self, character: Character):
        super().__init__(timeout=300)
        self.character = character

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm character deletion."""
        was_main = self.character.is_main
        character_name = self.character.name

        async with get_session() as session:
            await session.execute(
                delete(Character)
                .where(Character.id == self.character.id)
            )
            await session.commit()

        embed = discord.Embed(
            title="✅ Character Deleted",
            description=f"**{character_name}** has been permanently deleted.",
            color=discord.Color.green()
        )

        if was_main:
            embed.add_field(
                name="Note",
                value="This was your main character. You may want to set a new main character.",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel character deletion."""
        embed = discord.Embed(
            title="❌ Deletion Cancelled",
            description="Character deletion cancelled.",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterStatsView(discord.ui.View):
    """View for displaying guild character statistics."""

    def __init__(self, stats: Dict[str, Any]):
        super().__init__(timeout=300)
        self.stats = stats

    async def show_stats(self, interaction: discord.Interaction):
        """Display character statistics."""
        embed = discord.Embed(
            title="📊 Guild Character Statistics",
            description="Overview of guild member characters",
            color=discord.Color.green()
        )

        # General stats
        embed.add_field(
            name="📈 General Statistics",
            value=f"**Total Characters:** {self.stats['total_characters']}\n**Main Characters:** {self.stats['main_characters']}",
            inline=False
        )

        # Race distribution
        if self.stats['race_distribution']:
            race_text = []
            for race, count in sorted(self.stats['race_distribution'].items(), key=lambda x: x[1], reverse=True):
                race_text.append(f"**{race}:** {count}")

            embed.add_field(
                name="🧬 Race Distribution",
                value="\n".join(race_text[:10]),  # Top 10 races
                inline=True
            )

        # Archetype distribution
        if self.stats['archetype_distribution']:
            archetype_text = []
            for archetype, count in sorted(self.stats['archetype_distribution'].items(), key=lambda x: x[1], reverse=True):
                archetype_text.append(f"**{archetype}:** {count}")

            embed.add_field(
                name="⚔️ Archetype Distribution",
                value="\n".join(archetype_text[:10]),  # Top 10 archetypes
                inline=True
            )

        if not self.stats['race_distribution'] and not self.stats['archetype_distribution']:
            embed.add_field(
                name="ℹ️ No Data",
                value="No character data available yet. Encourage members to create character profiles!",
                inline=False
            )

        embed.set_footer(text="💡 Character data helps with guild planning and organization")

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Refresh Stats", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh character statistics."""
        new_stats = await get_character_statistics(interaction.guild_id)
        self.stats = new_stats

        await self.show_stats(interaction)


# Admin character management views (for admins to manage all member characters)

class AdminCharacterBrowserView(discord.ui.View):
    """Admin view for browsing all member characters."""

    def __init__(self, member: Optional[discord.Member] = None):
        super().__init__(timeout=300)
        self.target_member = member
        self.characters: List[Character] = []

    async def show_admin_characters(self, interaction: discord.Interaction):
        """Show character browser for admins."""
        if self.target_member:
            await self.load_member_characters(interaction.guild_id, self.target_member.id)
            embed = discord.Embed(
                title=f"👤 {self.target_member.display_name}'s Characters",
                description="Admin view of member's characters",
                color=discord.Color.orange()
            )
        else:
            await self.load_all_characters(interaction.guild_id)
            embed = discord.Embed(
                title="👥 All Guild Characters",
                description="Admin overview of all member characters",
                color=discord.Color.orange()
            )

        if not self.characters:
            embed.add_field(
                name="No Characters",
                value="No characters found.",
                inline=False
            )
        else:
            char_summary = []
            for char in self.characters[:10]:  # Show first 10
                owner = interaction.guild.get_member(char.user_id) if hasattr(char, 'user_id') else None
                owner_name = owner.display_name if owner else "Unknown"
                main_indicator = "⭐ " if char.is_main else ""
                race_text = f" ({char.race})" if char.race else ""

                char_summary.append(f"{main_indicator}**{char.name}**{race_text} - {owner_name}")

            embed.add_field(
                name="Characters",
                value="\n".join(char_summary),
                inline=False
            )

            if len(self.characters) > 10:
                embed.add_field(
                    name="Note",
                    value=f"Showing 10 of {len(self.characters)} characters. Use character statistics for full overview.",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_member_characters(self, guild_id: int, user_id: int):
        """Load characters for a specific member."""
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == user_id,
                        User.guild_id == guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()

            if db_user:
                result = await session.execute(
                    select(Character).where(Character.user_id == db_user.id)
                    .order_by(Character.is_main.desc(), Character.created_at)
                )
                self.characters = result.scalars().all()

    async def load_all_characters(self, guild_id: int):
        """Load all characters in the guild."""
        async with get_session() as session:
            result = await session.execute(
                select(Character).where(Character.guild_id == guild_id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            self.characters = result.scalars().all()

    @discord.ui.button(label="Character Statistics", style=discord.ButtonStyle.primary, emoji="📊")
    async def show_character_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed character statistics."""
        stats = await get_character_statistics(interaction.guild_id)
        view = CharacterStatsView(stats)
        await view.show_stats(interaction)