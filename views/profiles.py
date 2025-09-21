"""
Character profile management views for the Guild Management Bot
"""
import discord
from sqlalchemy import select, and_, update
from typing import List, Optional

from database import User, Character, get_session
from utils.permissions import PermissionChecker


class CharacterManagerView(discord.ui.View):
    """Main character management interface for users."""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.characters: List[Character] = []
        self.current_page = 0
    
    async def load_characters(self, guild_id: int):
        """Load user's characters."""
        async with get_session() as session:
            # Ensure user exists
            result = await session.execute(
                select(User).where(
                    and_(
                        User.discord_user_id == self.user_id,
                        User.guild_id == guild_id
                    )
                )
            )
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(discord_user_id=self.user_id, guild_id=guild_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # Load characters
            result = await session.execute(
                select(Character).where(Character.user_id == user.id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            self.characters = result.scalars().all()
    
    async def show_characters(self, interaction: discord.Interaction):
        """Display character list."""
        await self.load_characters(interaction.guild_id)
        
        embed = discord.Embed(
            title="👤 My Characters",
            color=discord.Color.blue()
        )
        
        if not self.characters:
            embed.description = "You don't have any characters yet. Click 'Add Character' to create one!"
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
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons based on current state."""
        self.clear_items()
        
        # Add character button
        add_button = discord.ui.Button(
            label="Add Character",
            style=discord.ButtonStyle.primary,
            emoji="➕"
        )
        add_button.callback = self.add_character
        self.add_item(add_button)
        
        if self.characters:
            # Character selection dropdown
            options = []
            for i, char in enumerate(self.characters[:25]):  # Discord limit
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
    
    async def add_character(self, interaction: discord.Interaction):
        """Open add character modal."""
        modal = AddCharacterModal(self.user_id)
        await interaction.response.send_modal(modal)
    
    async def select_character(self, interaction: discord.Interaction):
        """Handle character selection."""
        character_id = int(interaction.data['values'][0])
        
        # Find the character
        character = next((c for c in self.characters if c.id == character_id), None)
        if not character:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return
        
        view = CharacterActionView(character, self)
        
        embed = discord.Embed(
            title=f"👤 {character.name}",
            color=discord.Color.green() if character.is_main else discord.Color.blue()
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


class AddCharacterModal(discord.ui.Modal):
    """Modal for adding a new character."""
    
    def __init__(self, user_id: int):
        super().__init__(title="Add New Character")
        self.user_id = user_id
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character's name...",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class (Optional)",
            placeholder="e.g., Warrior, Mage, Rogue...",
            required=False,
            max_length=100
        )
        self.add_item(self.archetype_input)
        
        self.notes_input = discord.ui.TextInput(
            label="Build Notes (Optional)",
            placeholder="Describe your character build, playstyle, etc...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle character creation."""
        name = self.name_input.value.strip()
        archetype = self.archetype_input.value.strip() if self.archetype_input.value else None
        notes = self.notes_input.value.strip() if self.notes_input.value else None
        
        async with get_session() as session:
            # Get or create user
            result = await session.execute(
                select(User).where(
                    and_(
                        User.discord_user_id == self.user_id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(discord_user_id=self.user_id, guild_id=interaction.guild_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # Check for duplicate name
            result = await session.execute(
                select(Character).where(
                    and_(
                        Character.user_id == user.id,
                        Character.name.ilike(name)
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                embed = discord.Embed(
                    title="❌ Duplicate Name",
                    description=f"You already have a character named '{name}'. Please choose a different name.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if this should be the main character (first character)
            result = await session.execute(
                select(Character).where(Character.user_id == user.id)
            )
            existing_characters = result.scalars().all()
            is_main = len(existing_characters) == 0
            
            # Create character
            character = Character(
                user_id=user.id,
                guild_id=interaction.guild_id,
                name=name,
                archetype=archetype,
                build_notes=notes,
                is_main=is_main
            )
            session.add(character)
            await session.commit()
            
            main_text = " (set as main character)" if is_main else ""
            embed = discord.Embed(
                title="✅ Character Created",
                description=f"Created character **{name}**{main_text}!",
                color=discord.Color.green()
            )
            
            if archetype:
                embed.add_field(name="Archetype", value=archetype, inline=True)
            
            if notes:
                embed.add_field(name="Build Notes", value=notes[:200] + "..." if len(notes) > 200 else notes, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)


class CharacterActionView(discord.ui.View):
    """Action view for a specific character."""
    
    def __init__(self, character: Character, parent_view: CharacterManagerView):
        super().__init__(timeout=300)
        self.character = character
        self.parent_view = parent_view
    
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Edit character details."""
        modal = EditCharacterModal(self.character)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set as Main", style=discord.ButtonStyle.primary, emoji="⭐")
    async def set_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set this character as main."""
        if self.character.is_main:
            await interaction.response.send_message(
                "This character is already your main character!",
                ephemeral=True
            )
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
            description=f"**{self.character.name}** is now your main character!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete character with confirmation."""
        view = ConfirmDeleteView(self.character)
        
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete **{self.character.name}**?\n\nThis action cannot be undone.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Back to List", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to character list."""
        await self.parent_view.show_characters(interaction)


class EditCharacterModal(discord.ui.Modal):
    """Modal for editing character details."""
    
    def __init__(self, character: Character):
        super().__init__(title=f"Edit {character.name}")
        self.character = character
        
        self.name_input = discord.ui.TextInput(
            label="Character Name",
            default=character.name,
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.archetype_input = discord.ui.TextInput(
            label="Archetype/Class",
            default=character.archetype or "",
            required=False,
            max_length=100
        )
        self.add_item(self.archetype_input)
        
        self.notes_input = discord.ui.TextInput(
            label="Build Notes",
            default=character.build_notes or "",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000
        )
        self.add_item(self.notes_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle character update."""
        name = self.name_input.value.strip()
        archetype = self.archetype_input.value.strip() if self.archetype_input.value else None
        notes = self.notes_input.value.strip() if self.notes_input.value else None
        
        async with get_session() as session:
            # Check for duplicate name (excluding current character)
            if name != self.character.name:
                result = await session.execute(
                    select(Character).where(
                        and_(
                            Character.user_id == self.character.user_id,
                            Character.name.ilike(name),
                            Character.id != self.character.id
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    embed = discord.Embed(
                        title="❌ Duplicate Name",
                        description=f"You already have a character named '{name}'. Please choose a different name.",
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
                    build_notes=notes
                )
            )
            await session.commit()
        
        embed = discord.Embed(
            title="✅ Character Updated",
            description=f"Successfully updated **{name}**!",
            color=discord.Color.green()
        )
        
        if archetype:
            embed.add_field(name="Archetype", value=archetype, inline=True)
        
        if notes:
            embed.add_field(name="Build Notes", value=notes[:200] + "..." if len(notes) > 200 else notes, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmDeleteView(discord.ui.View):
    """Confirmation view for character deletion."""
    
    def __init__(self, character: Character):
        super().__init__(timeout=300)
        self.character = character
    
    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm character deletion."""
        async with get_session() as session:
            # If this was the main character, set another as main
            if self.character.is_main:
                result = await session.execute(
                    select(Character).where(
                        and_(
                            Character.user_id == self.character.user_id,
                            Character.id != self.character.id
                        )
                    ).limit(1)
                )
                next_character = result.scalar_one_or_none()
                
                if next_character:
                    await session.execute(
                        update(Character)
                        .where(Character.id == next_character.id)
                        .values(is_main=True)
                    )
            
            # Delete character
            result = await session.execute(
                select(Character).where(Character.id == self.character.id)
            )
            character = result.scalar_one()
            await session.delete(character)
            await session.commit()
        
        embed = discord.Embed(
            title="🗑️ Character Deleted",
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
                        User.discord_user_id == user.id,
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
        
        # Log action
        bot = interaction.client
        await bot.log_action(
            interaction.guild_id,
            "Character Main Status Change",
            interaction.user,
            self.owner,
            f"Set '{self.character.name}' as main character"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Delete Character", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_character(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete character (admin action)."""
        view = AdminConfirmDeleteView(self.character, self.owner)
        
        embed = discord.Embed(
            title="⚠️ Admin Action: Confirm Deletion",
            description=(
                f"Are you sure you want to delete **{self.character.name}** "
                f"belonging to {self.owner.mention}?\n\n"
                "This action cannot be undone and will be logged."
            ),
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AdminConfirmDeleteView(discord.ui.View):
    """Admin confirmation for character deletion."""
    
    def __init__(self, character: Character, owner: discord.Member):
        super().__init__(timeout=300)
        self.character = character
        self.owner = owner
    
    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm character deletion."""
        async with get_session() as session:
            # If this was the main character, set another as main
            if self.character.is_main:
                result = await session.execute(
                    select(Character).where(
                        and_(
                            Character.user_id == self.character.user_id,
                            Character.id != self.character.id
                        )
                    ).limit(1)
                )
                next_character = result.scalar_one_or_none()
                
                if next_character:
                    await session.execute(
                        update(Character)
                        .where(Character.id == next_character.id)
                        .values(is_main=True)
                    )
            
            # Delete character
            result = await session.execute(
                select(Character).where(Character.id == self.character.id)
            )
            character = result.scalar_one()
            await session.delete(character)
            await session.commit()
        
        embed = discord.Embed(
            title="🗑️ Character Deleted (Admin Action)",
            description=f"Deleted **{self.character.name}** belonging to {self.owner.mention}.",
            color=discord.Color.red()
        )
        
        # Log action
        bot = interaction.client
        await bot.log_action(
            interaction.guild_id,
            "Character Deletion",
            interaction.user,
            self.owner,
            f"Deleted character '{self.character.name}'"
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