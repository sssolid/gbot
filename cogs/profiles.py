"""
Profiles cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_

from database import User, Character, get_session
from views.profiles import CharacterManagerView
from utils.permissions import PermissionChecker


class ProfilesCog(commands.Cog):
    """Handles character profile commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="characters", description="Manage your character profiles")
    async def characters_command(self, interaction: discord.Interaction):
        """Open character management interface."""
        view = CharacterManagerView(interaction.user.id)
        await view.show_characters(interaction)
    
    @app_commands.command(name="profile", description="View a user's character profile")
    @app_commands.describe(user="User whose profile to view")
    async def profile_command(self, interaction: discord.Interaction, user: discord.Member = None):
        """View character profile for yourself or another user."""
        target_user = user or interaction.user
        
        if target_user.bot:
            embed = discord.Embed(
                title="❌ Bot Account",
                description="Profiles are not available for bot accounts.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Load user's characters
        async with get_session() as session:
            result = await session.execute(
                select(User).where(
                    and_(
                        User.user_id == target_user.id,
                        User.guild_id == interaction.guild_id
                    )
                )
            )
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                if target_user == interaction.user:
                    embed = discord.Embed(
                        title="👤 Your Profile",
                        description="You haven't created any characters yet. Use `/characters` to get started!",
                        color=discord.Color.blue()
                    )
                else:
                    embed = discord.Embed(
                        title=f"👤 {target_user.display_name}'s Profile",
                        description="This user hasn't created any characters yet.",
                        color=discord.Color.blue()
                    )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            result = await session.execute(
                select(Character).where(Character.user_id == db_user.id)
                .order_by(Character.is_main.desc(), Character.created_at)
            )
            characters = result.scalars().all()
        
        if target_user == interaction.user:
            embed = discord.Embed(
                title="👤 Your Character Profile",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title=f"👤 {target_user.display_name}'s Profile",
                color=discord.Color.blue()
            )
        
        if not characters:
            if target_user == interaction.user:
                embed.description = "You haven't created any characters yet. Use `/characters` to create one!"
            else:
                embed.description = "This user hasn't created any characters yet."
        else:
            for char in characters[:5]:  # Show up to 5 characters
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
            
            if len(characters) > 5:
                embed.add_field(
                    name="",
                    value=f"*...and {len(characters) - 5} more character(s)*",
                    inline=False
                )
        
        embed.add_field(
            name="Member Since",
            value=discord.utils.format_dt(target_user.joined_at, 'D') if target_user.joined_at else "Unknown",
            inline=True
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Add management button for own profile
        view = None
        if target_user == interaction.user and characters:
            view = QuickProfileView(interaction.user.id)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="main_character", description="View your main character")
    async def main_character_command(self, interaction: discord.Interaction):
        """Display the user's main character."""
        async with get_session() as session:
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
                    title="👤 No Main Character",
                    description="You haven't created any characters yet. Use `/characters` to create one!",
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
            
            if main_character.archetype:
                embed.add_field(
                    name="Archetype",
                    value=main_character.archetype,
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="character_stats", description="View character statistics for the server (Admin only)")
    async def character_stats(self, interaction: discord.Interaction):
        """Show character statistics for the server."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view character statistics",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with get_session() as session:
            # Count users with characters
            result = await session.execute(
                select(User).where(User.guild_id == interaction.guild_id)
            )
            users_with_profiles = result.scalars().all()
            
            # Count total characters
            total_characters = 0
            archetype_counts = {}
            
            for user in users_with_profiles:
                result = await session.execute(
                    select(Character).where(Character.user_id == user.id)
                )
                user_characters = result.scalars().all()
                total_characters += len(user_characters)
                
                for char in user_characters:
                    if char.archetype:
                        archetype_counts[char.archetype] = archetype_counts.get(char.archetype, 0) + 1
        
        embed = discord.Embed(
            title="📊 Character Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📈 Overview",
            value=(
                f"**Users with profiles:** {len(users_with_profiles)}\n"
                f"**Total characters:** {total_characters}\n"
                f"**Average per user:** {total_characters / len(users_with_profiles):.1f}" if users_with_profiles else "0"
            ),
            inline=False
        )
        
        if archetype_counts:
            # Show top 10 archetypes
            sorted_archetypes = sorted(archetype_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            archetype_text = []
            
            for archetype, count in sorted_archetypes:
                percentage = (count / total_characters * 100) if total_characters > 0 else 0
                archetype_text.append(f"**{archetype}:** {count} ({percentage:.1f}%)")
            
            embed.add_field(
                name="🎭 Popular Archetypes",
                value="\n".join(archetype_text),
                inline=False
            )
        
        embed.set_footer(text=f"Data for {interaction.guild.name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class QuickProfileView(discord.ui.View):
    """Quick actions for user's own profile."""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
    
    @discord.ui.button(label="Manage Characters", style=discord.ButtonStyle.primary, emoji="✏️")
    async def manage_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open character management interface."""
        view = CharacterManagerView(self.user_id)
        await view.show_characters(interaction)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ProfilesCog(bot))