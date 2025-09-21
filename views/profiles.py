"""
Character profile management views for the Guild Management Bot - FIXED VERSION
"""
import discord
from sqlalchemy import select, and_, update, delete
from typing import List, Optional
from datetime import datetime

from database import User, Character, get_session
from utils.permissions import PermissionChecker


class CharacterManagerView(discord.ui.View):
    """Main character management view."""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.characters: List[Character] = []
    
    async def show_characters(self, interaction: discord.Interaction):
        """Display user's characters."""
        await self.load_characters(interaction.guild_id)
        
        embed = discord.Embed(
            title="👤 My Characters",
            description="Manage your character profiles",
            color=discord.Color.blue()
        )
        
        if not self.characters:
            embed.add_field(
                name="No Characters",
                value="You haven't created any characters yet. Click 'Create Character' to get started!",
                inline=False
            )
        else:
            for char in self.characters:
                main_indicator = "⭐ " if char.is_main else ""
                archetype_text = f" ({char.archetype})" if char.archetype else ""
                
                value = f"**{main_indicator}{char.name}**{archetype_text}"
                if char.build_notes:
                    value += f"\n*{char.build_notes[:100]}{'...' if len(char.build_notes) > 100 else ''}*"
                
                embed.add_field(
                    name=f"Character {len([f for f in embed.fields]) + 1}",
                    value=value,
                    inline=False
                )
        
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
        
        if character.archetype:
            embed.add_field(name="Archetype", value=character.archetype, inline=True)
        
        if character.is_main:
            embed.add_field(name="Status", value="⭐ Main Character", inline=True)
        
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
        """Create a new character."""
        modal = CharacterCreationModal(self.user_id)
        await interaction.response.send_modal(modal)
    
    async def on_view_start(self):
        """Update the select menu with current characters."""
        if self.characters:
            options = []
            for char in self.characters[:25]:  # Discord limit
                main_indicator = "⭐ " if char.is_main else ""
                archetype_text = f" ({char.archetype})" if char.archetype else ""
                
                options.append(discord.SelectOption(
                    label=f"{main_indicator}{char.name}",
                    description=f"ID: {char.id}{archetype_text}",
                    value=str(char.id),
                    emoji="⭐" if char.is_main else "👤"
                ))
            
            self.character_select.options = options
            self.character_select.placeholder = "Select a character to manage..."
        else:
            self.character_select.options = [discord.SelectOption(label="No characters", value="none")]
            self.character_select.placeholder = "No characters to manage"


class CharacterCreationModal(discord.ui.Modal):
    """Modal for creating a new character."""
    
    def __init__(self, user_id: int):
        super().__init__(title="Create New Character")
        self.user_id = user_id
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character's name...",
            required=True,
            max_length=100
        )
        
        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            placeholder="e.g., Warrior, Mage, Rogue, etc.",
            required=False,
            max_length=50
        )
        
        self.notes_input = discord.ui.TextInput(
            label="Build Notes",
            placeholder="Describe your character's build, playstyle, etc.",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        
        self.add_item(self.name_input)
        self.add_item(self.archetype_input)
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle character creation submission."""
        name = self.name_input.value.strip()
        archetype = self.archetype_input.value.strip() or None
        build_notes = self.notes_input.value.strip() or None
        
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
                name=name,
                archetype=archetype,
                build_notes=build_notes,
                is_main=is_main,
                user_id=db_user.id,
                created_at=datetime.utcnow()
            )
            
            session.add(character)
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Character Created",
            description=f"Successfully created **{name}**!",
            color=discord.Color.green()
        )
        
        if is_main:
            embed.add_field(
                name="Main Character",
                value="⭐ This character has been set as your main character since it's your first one.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterActionView(discord.ui.View):
    """Actions for a specific character."""
    
    def __init__(self, character: Character):
        super().__init__(timeout=300)
        self.character = character
        
        # Disable "Set as Main" if already main
        if character.is_main:
            self.set_main.disabled = True
            self.set_main.label = "Currently Main"
    
    @discord.ui.button(label="Set as Main", style=discord.ButtonStyle.primary, emoji="⭐")
    async def set_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set character as main."""
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
                .values(is_main=False)
            )
            
            # Set new main
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(is_main=True)
            )
            
            await session.commit()
        
        embed = discord.Embed(
            title="⭐ Main Character Updated",
            description=f"**{self.character.name}** is now your main character.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit character details."""
        modal = CharacterEditModal(self.character)
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


class CharacterEditModal(discord.ui.Modal):
    """Modal for editing a character."""
    
    def __init__(self, character: Character):
        super().__init__(title=f"Edit {character.name}")
        self.character = character
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            default=character.name,
            required=True,
            max_length=100
        )
        
        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            default=character.archetype or "",
            required=False,
            max_length=50
        )
        
        self.notes_input = discord.ui.TextInput(
            label="Build Notes",
            default=character.build_notes or "",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        
        self.add_item(self.name_input)
        self.add_item(self.archetype_input)
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle character edit submission."""
        name = self.name_input.value.strip()
        archetype = self.archetype_input.value.strip() or None
        build_notes = self.notes_input.value.strip() or None
        
        async with get_session() as session:
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(
                    name=name,
                    archetype=archetype,
                    build_notes=build_notes
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
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm character deletion."""
        async with get_session() as session:
            await session.execute(
                delete(Character).where(Character.id == self.character.id)
            )
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Character Deleted",
            description=f"**{self.character.name}** has been deleted.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel deletion."""
        embed = discord.Embed(
            title="❌ Deletion Cancelled",
            description="Character deletion has been cancelled.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ProfileAdminView(discord.ui.View):
    """Admin view for managing profiles."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    async def show_admin_interface(self, interaction: discord.Interaction):
        """Show the admin interface for profile management."""
        embed = discord.Embed(
            title="👤 Profiles Administration",
            description="Select a user to manage their character profiles",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Available Actions",
            value=(
                "• View user's character profiles\n"
                "• Set character as main\n"
                "• Edit character details\n"
                "• Delete characters\n"
                "• View creation timestamps"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select a user to manage their profiles..."
    )
    async def user_select(self, interaction: discord.Interaction, menu: discord.ui.UserSelect):
        """Select a user to manage."""
        user = menu.values[0]
        
        # Load user's characters
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == user.id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                embed = discord.Embed(
                    title="👤 User Profile",
                    description=f"{user.mention} has no characters registered.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            result = await session.execute(
                select(Character).where(Character.user_id == db_user.id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            characters = result.scalars().all()
        
        embed = discord.Embed(
            title=f"👤 {user.display_name}'s Characters",
            color=discord.Color.blue()
        )
        
        if not characters:
            embed.description = "This user has no characters."
        else:
            for char in characters:
                main_indicator = "⭐ " if char.is_main else ""
                archetype_text = f" ({char.archetype})" if char.archetype else ""
                
                value = f"**{main_indicator}{char.name}**{archetype_text}"
                if char.build_notes:
                    value += f"\n*{char.build_notes[:100]}{'...' if len(char.build_notes) > 100 else ''}*"
                
                embed.add_field(
                    name=f"Character {len([f for f in embed.fields]) + 1}",
                    value=value,
                    inline=False
                )
        
        view = UserProfileAdminView(user, characters)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class UserProfileAdminView(discord.ui.View):
    """Admin actions for a specific user's profile."""
    
    def __init__(self, user: discord.Member, characters: List[Character]):
        super().__init__(timeout=300)
        self.user = user
        self.characters = characters
        
        if characters:
            # Add character selection dropdown
            options = []
            for char in characters[:25]:
                main_indicator = "⭐ " if char.is_main else ""
                archetype_text = f" ({char.archetype})" if char.archetype else ""
                
                options.append(discord.SelectOption(
                    label=f"{main_indicator}{char.name}",
                    description=f"ID: {char.id}{archetype_text}",
                    value=str(char.id),
                    emoji="⭐" if char.is_main else "👤"
                ))
            
            if options:
                select = discord.ui.Select(
                    placeholder="Select a character to manage...",
                    options=options
                )
                select.callback = self.select_character
                self.add_item(select)
    
    async def select_character(self, interaction: discord.Interaction):
        """Handle character selection for admin actions."""
        character_id = int(interaction.data['values'][0])
        character = next((c for c in self.characters if c.id == character_id), None)
        
        if not character:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return
        
        view = AdminCharacterActionView(character, self.user)
        
        embed = discord.Embed(
            title=f"👤 {character.name} (Admin View)",
            description=f"Character owned by {self.user.mention}",
            color=discord.Color.orange()
        )
        
        if character.archetype:
            embed.add_field(name="Archetype", value=character.archetype, inline=True)
        
        if character.is_main:
            embed.add_field(name="Status", value="⭐ Main Character", inline=True)
        
        if character.build_notes:
            embed.add_field(name="Build Notes", value=character.build_notes, inline=False)
        
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(character.created_at, 'F'),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AdminCharacterActionView(discord.ui.View):
    """Admin actions for a specific character."""
    
    def __init__(self, character: Character, owner: discord.Member):
        super().__init__(timeout=300)
        self.character = character
        self.owner = owner
    
    @discord.ui.button(label="Set as Main", style=discord.ButtonStyle.primary, emoji="⭐")
    async def set_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set character as main (admin action)."""
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
                .values(is_main=False)
            )
            
            # Set new main
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(is_main=True)
            )
            
            await session.commit()
        
        embed = discord.Embed(
            title="⭐ Main Character Updated (Admin Action)",
            description=f"Set **{self.character.name}** as {self.owner.mention}'s main character.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Edit Character", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit character (admin action)."""
        modal = AdminCharacterEditModal(self.character, self.owner)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete Character", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete character (admin action)."""
        view = AdminCharacterDeletionView(self.character, self.owner)
        
        embed = discord.Embed(
            title="⚠️ Delete Character (Admin Action)",
            description=f"Are you sure you want to delete **{self.character.name}** belonging to {self.owner.mention}?\n\nThis action cannot be undone.",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AdminCharacterEditModal(discord.ui.Modal):
    """Admin modal for editing a character."""
    
    def __init__(self, character: Character, owner: discord.Member):
        super().__init__(title=f"Edit {character.name} (Admin)")
        self.character = character
        self.owner = owner
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            default=character.name,
            required=True,
            max_length=100
        )
        
        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            default=character.archetype or "",
            required=False,
            max_length=50
        )
        
        self.notes_input = discord.ui.TextInput(
            label="Build Notes",
            default=character.build_notes or "",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        
        self.add_item(self.name_input)
        self.add_item(self.archetype_input)
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle admin character edit submission."""
        name = self.name_input.value.strip()
        archetype = self.archetype_input.value.strip() or None
        build_notes = self.notes_input.value.strip() or None
        
        async with get_session() as session:
            await session.execute(
                update(Character)
                .where(Character.id == self.character.id)
                .values(
                    name=name,
                    archetype=archetype,
                    build_notes=build_notes
                )
            )
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Character Updated (Admin Action)",
            description=f"Successfully updated **{name}** for {self.owner.mention}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AdminCharacterDeletionView(discord.ui.View):
    """Admin confirmation view for character deletion."""
    
    def __init__(self, character: Character, owner: discord.Member):
        super().__init__(timeout=300)
        self.character = character
        self.owner = owner
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm character deletion (admin action)."""
        async with get_session() as session:
            await session.execute(
                delete(Character).where(Character.id == self.character.id)
            )
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Character Deleted (Admin Action)",
            description=f"**{self.character.name}** belonging to {self.owner.mention} has been deleted.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel deletion."""
        embed = discord.Embed(
            title="❌ Deletion Cancelled",
            description="Character deletion has been cancelled.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)