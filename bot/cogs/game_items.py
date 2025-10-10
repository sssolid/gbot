# File: cogs/game_items.py
# Location: /bot/cogs/game_items.py

import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from typing import Optional

from models import Guild, Game
from models_game_db import GameItem, GameItemCategory, ItemType
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class GameItemsCog(commands.Cog):
    """Manages game item database (weapons, armor, NPCs, resources, etc.)"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="item_search", description="Search for game items/entities")
    @app_commands.guild_only()
    @app_commands.describe(
        query="Item name to search for",
        game="Game name (optional)",
        item_type="Type of item (optional)"
    )
    async def item_search(
            self,
            interaction: discord.Interaction,
            query: str,
            game: str = None,
            item_type: str = None
    ):
        """Search for items in the database"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            # Build query
            filters = [GameItem.name.ilike(f"%{query}%")]

            if game:
                game_obj = session.query(Game).filter_by(
                    guild_id=guild.id,
                    name=game
                ).first()
                if game_obj:
                    filters.append(GameItem.game_id == game_obj.id)

            if item_type:
                try:
                    filters.append(GameItem.item_type == ItemType(item_type.lower()))
                except ValueError:
                    pass

            items = session.query(GameItem).filter(*filters).limit(10).all()

            if not items:
                await interaction.response.send_message(
                    f"🔍 No items found matching '{query}'",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🔍 Search Results for '{query}'",
                description=f"Found {len(items)} item(s)",
                color=discord.Color.blue()
            )

            for item in items[:5]:
                value_parts = []
                value_parts.append(f"**Type:** {item.item_type.value.title()}")
                value_parts.append(f"**Game:** {item.game.name}")

                if item.description:
                    value_parts.append(
                        f"*{item.description[:100]}...*" if len(item.description) > 100 else f"*{item.description}*")

                embed.add_field(
                    name=f"{item.name} (ID: {item.id})",
                    value="\n".join(value_parts),
                    inline=False
                )

            if len(items) > 5:
                embed.set_footer(text=f"Showing 5 of {len(items)} results. Use /item_view <id> for details")
            else:
                embed.set_footer(text="Use /item_view <id> for detailed information")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="item_view", description="View detailed information about an item")
    @app_commands.guild_only()
    @app_commands.describe(item_id="Item ID from search results")
    async def item_view(self, interaction: discord.Interaction, item_id: int):
        """View detailed item information"""
        with db.session_scope() as session:
            item = session.query(GameItem).filter_by(id=item_id).first()

            if not item:
                await interaction.response.send_message("❌ Item not found.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"{item.name}",
                description=item.description or "No description available",
                color=discord.Color.gold()
            )

            embed.add_field(name="Game", value=item.game.name, inline=True)
            embed.add_field(name="Type", value=item.item_type.value.title(), inline=True)

            if item.category:
                embed.add_field(name="Category", value=item.category.name, inline=True)

            # Display stats
            if item.stats:
                stats_text = []
                for key, value in item.stats.items():
                    stats_text.append(f"**{key.replace('_', ' ').title()}:** {value}")

                embed.add_field(
                    name="📊 Statistics",
                    value="\n".join(stats_text) if stats_text else "No stats",
                    inline=False
                )

            # Display tags
            if item.tags:
                embed.add_field(
                    name="🏷️ Tags",
                    value=item.tags,
                    inline=False
                )

            # Set images
            if item.icon_url:
                embed.set_thumbnail(url=item.icon_url)

            if item.image_url:
                embed.set_image(url=item.image_url)

            embed.set_footer(text=f"Item ID: {item.id} | Added: {item.created_at.strftime('%Y-%m-%d')}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="item_add", description="Add a new item to the database")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def item_add(self, interaction: discord.Interaction):
        """Add new item - opens modal"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            if not guild:
                await interaction.response.send_message("❌ Server not configured.", ephemeral=True)
                return

            games = session.query(Game).filter_by(guild_id=guild.id, enabled=True).all()

            if not games:
                await interaction.response.send_message(
                    "❌ No games configured. Use `/add_game` first.",
                    ephemeral=True
                )
                return

        if len(games) == 1:
            modal = AddItemModal(self.bot, games[0].id, games[0].name)
            await interaction.response.send_modal(modal)
        else:
            view = GameSelectView(games)
            await interaction.response.send_message(
                "Select a game for this item:",
                view=view,
                ephemeral=True
            )

    @app_commands.command(name="item_edit", description="Edit an existing item")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(item_id="Item ID to edit")
    async def item_edit(self, interaction: discord.Interaction, item_id: int):
        """Edit item"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            item = session.query(GameItem).filter_by(id=item_id).first()

            if not item:
                await interaction.response.send_message("❌ Item not found.", ephemeral=True)
                return

            modal = EditItemModal(self.bot, item)
            await interaction.response.send_modal(modal)

    @app_commands.command(name="item_delete", description="Delete an item from the database")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(item_id="Item ID to delete")
    async def item_delete(self, interaction: discord.Interaction, item_id: int):
        """Delete item"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            item = session.query(GameItem).filter_by(id=item_id).first()

            if not item:
                await interaction.response.send_message("❌ Item not found.", ephemeral=True)
                return

            item_name = item.name
            session.delete(item)
            session.commit()

        await interaction.response.send_message(
            f"✅ Deleted item: **{item_name}**",
            ephemeral=True
        )

    @app_commands.command(name="item_category_add", description="Add a category for organizing items")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        game="Game name",
        name="Category name",
        item_type="Type of items in this category"
    )
    async def category_add(
            self,
            interaction: discord.Interaction,
            game: str,
            name: str,
            item_type: str
    ):
        """Add item category"""
        if not await self._check_admin(interaction):
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            game_obj = session.query(Game).filter_by(guild_id=guild.id, name=game).first()

            if not game_obj:
                await interaction.response.send_message("❌ Game not found.", ephemeral=True)
                return

            try:
                item_type_enum = ItemType(item_type.lower())
            except ValueError:
                valid_types = ", ".join([t.value for t in ItemType])
                await interaction.response.send_message(
                    f"❌ Invalid item type. Valid types: {valid_types}",
                    ephemeral=True
                )
                return

            category = GameItemCategory(
                game_id=game_obj.id,
                name=name,
                item_type=item_type_enum
            )
            session.add(category)
            session.commit()

        await interaction.response.send_message(
            f"✅ Created category: **{name}** for {game}",
            ephemeral=True
        )

    @app_commands.command(name="item_list", description="List all items in a game")
    @app_commands.guild_only()
    @app_commands.describe(
        game="Game name",
        item_type="Filter by type (optional)"
    )
    async def item_list(
            self,
            interaction: discord.Interaction,
            game: str,
            item_type: str = None
    ):
        """List items"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()
            game_obj = session.query(Game).filter_by(guild_id=guild.id, name=game).first()

            if not game_obj:
                await interaction.response.send_message("❌ Game not found.", ephemeral=True)
                return

            filters = [GameItem.game_id == game_obj.id]

            if item_type:
                try:
                    filters.append(GameItem.item_type == ItemType(item_type.lower()))
                except ValueError:
                    pass

            items = session.query(GameItem).filter(*filters).order_by(GameItem.name).limit(25).all()

            if not items:
                await interaction.response.send_message(
                    f"📭 No items found for {game}",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"📋 Items in {game}",
                description=f"Showing {len(items)} item(s)" + (f" of type {item_type}" if item_type else ""),
                color=discord.Color.blue()
            )

            # Group by type
            by_type = {}
            for item in items:
                type_name = item.item_type.value.title()
                if type_name not in by_type:
                    by_type[type_name] = []
                by_type[type_name].append(item)

            for type_name, type_items in by_type.items():
                items_text = "\n".join([f"• {item.name} (ID: {item.id})" for item in type_items[:10]])
                if len(type_items) > 10:
                    items_text += f"\n...and {len(type_items) - 10} more"

                embed.add_field(
                    name=f"{type_name} ({len(type_items)})",
                    value=items_text,
                    inline=False
                )

            embed.set_footer(text="Use /item_view <id> for details")

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


class GameSelectView(discord.ui.View):
    """View for selecting game"""

    def __init__(self, games):
        super().__init__(timeout=180)
        self.games = {str(game.id): game for game in games}

        options = [
            discord.SelectOption(label=game.name, value=str(game.id))
            for game in games
        ]

        select = discord.ui.Select(placeholder="Choose a game...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        game_id = int(interaction.data['values'][0])
        game = self.games[str(game_id)]

        modal = AddItemModal(interaction.client, game_id, game.name)
        await interaction.response.send_modal(modal)


class AddItemModal(discord.ui.Modal):
    """Modal for adding items"""

    def __init__(self, bot, game_id: int, game_name: str):
        super().__init__(title=f"Add Item - {game_name}")
        self.bot = bot
        self.game_id = game_id

        self.name = discord.ui.TextInput(
            label="Item Name",
            placeholder="e.g., Steel Longsword",
            required=True,
            max_length=200
        )
        self.add_item(self.name)

        self.item_type = discord.ui.TextInput(
            label="Type",
            placeholder="weapon, armor, resource, npc, creature, etc.",
            required=True,
            max_length=50
        )
        self.add_item(self.item_type)

        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Brief description...",
            style=discord.TextStyle.long,
            required=False,
            max_length=500
        )
        self.add_item(self.description)

        self.stats = discord.ui.TextInput(
            label="Stats (JSON format)",
            placeholder='{"damage": 50, "durability": 100, "weight": 5.2}',
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )
        self.add_item(self.stats)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            item_type_enum = ItemType(self.item_type.value.lower())
        except ValueError:
            valid_types = ", ".join([t.value for t in ItemType])
            await interaction.response.send_message(
                f"❌ Invalid item type. Valid types: {valid_types}",
                ephemeral=True
            )
            return

        stats_dict = None
        if self.stats.value:
            try:
                stats_dict = json.loads(self.stats.value)
            except json.JSONDecodeError:
                await interaction.response.send_message(
                    "❌ Invalid JSON format for stats.",
                    ephemeral=True
                )
                return

        with db.session_scope() as session:
            item = GameItem(
                game_id=self.game_id,
                name=self.name.value,
                item_type=item_type_enum,
                description=self.description.value if self.description.value else None,
                stats=stats_dict,
                created_by_user_id=interaction.user.id
            )
            session.add(item)
            session.commit()
            item_id = item.id

        embed = await create_embed(
            title="✅ Item Added",
            description=f"Successfully added **{self.name.value}**\nItem ID: {item_id}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditItemModal(discord.ui.Modal):
    """Modal for editing items"""

    def __init__(self, bot, item: GameItem):
        super().__init__(title=f"Edit Item - {item.name}")
        self.bot = bot
        self.item_id = item.id

        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Brief description...",
            style=discord.TextStyle.long,
            required=False,
            default=item.description or "",
            max_length=500
        )
        self.add_item(self.description)

        self.stats = discord.ui.TextInput(
            label="Stats (JSON format)",
            placeholder='{"damage": 50, "durability": 100}',
            style=discord.TextStyle.long,
            required=False,
            default=json.dumps(item.stats) if item.stats else "",
            max_length=1000
        )
        self.add_item(self.stats)

        self.tags = discord.ui.TextInput(
            label="Tags (comma-separated)",
            placeholder="steel, weapon, melee",
            required=False,
            default=item.tags or "",
            max_length=200
        )
        self.add_item(self.tags)

        self.icon_url = discord.ui.TextInput(
            label="Icon URL",
            placeholder="https://...",
            required=False,
            default=item.icon_url or "",
            max_length=500
        )
        self.add_item(self.icon_url)

    async def on_submit(self, interaction: discord.Interaction):
        stats_dict = None
        if self.stats.value:
            try:
                stats_dict = json.loads(self.stats.value)
            except json.JSONDecodeError:
                await interaction.response.send_message(
                    "❌ Invalid JSON format for stats.",
                    ephemeral=True
                )
                return

        with db.session_scope() as session:
            item = session.query(GameItem).filter_by(id=self.item_id).first()

            item.description = self.description.value if self.description.value else None
            item.stats = stats_dict
            item.tags = self.tags.value if self.tags.value else None
            item.icon_url = self.icon_url.value if self.icon_url.value else None

            session.commit()
            item_name = item.name

        await interaction.response.send_message(
            f"✅ Updated **{item_name}**",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(GameItemsCog(bot))