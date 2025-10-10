# File: cogs/structures.py
# Location: /bot/cogs/structures.py

import discord
from discord.ext import commands
from discord import app_commands
import logging

from models_rpg import UserProfile, RPGItem, InventoryItem
from models_rpg import PlayerStructure, StructureStorage, StructureType
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class StructuresCog(commands.Cog):
    """Player housing and storage management"""

    def __init__(self, bot):
        self.bot = bot

        # Structure definitions
        self.structure_info = {
            StructureType.SMALL_STORAGE: {
                "name": "Small Storage Chest",
                "emoji": "📦",
                "capacity": 10,
                "cost": 500,
                "upkeep": 0,
                "description": "A basic storage chest"
            },
            StructureType.MEDIUM_STORAGE: {
                "name": "Medium Storage",
                "emoji": "🗄️",
                "capacity": 25,
                "cost": 2000,
                "upkeep": 50,
                "description": "A larger storage solution"
            },
            StructureType.LARGE_STORAGE: {
                "name": "Large Storage",
                "emoji": "🏪",
                "capacity": 50,
                "cost": 5000,
                "upkeep": 100,
                "description": "Substantial storage space"
            },
            StructureType.WAREHOUSE: {
                "name": "Warehouse",
                "emoji": "🏭",
                "capacity": 100,
                "cost": 15000,
                "upkeep": 250,
                "description": "Massive storage facility"
            },
            StructureType.VAULT: {
                "name": "Secure Vault",
                "emoji": "🏦",
                "capacity": 75,
                "cost": 10000,
                "upkeep": 200,
                "description": "Ultra-secure storage"
            }
        }

    @app_commands.command(name="structures", description="View your structures")
    @app_commands.guild_only()
    async def structures(self, interaction: discord.Interaction):
        """View owned structures"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ Create your profile first with `/profile`",
                    ephemeral=True
                )
                return

            structures = session.query(PlayerStructure).filter_by(
                profile_id=profile.id,
                is_active=True
            ).all()

            if not structures:
                await interaction.response.send_message(
                    "🏗️ You don't have any structures yet!\n"
                    "Use `/structure_build` to construct one.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🏠 Your Structures",
                description=f"You own {len(structures)} structure(s)",
                color=discord.Color.green()
            )

            for structure in structures:
                info = self.structure_info[structure.structure_type]

                usage_pct = (structure.current_usage / structure.max_capacity) * 100
                usage_bar = self._create_bar(usage_pct)

                embed.add_field(
                    name=f"{info['emoji']} {info['name']} (ID: {structure.id})",
                    value=(
                        f"**Capacity:** {usage_bar} {structure.current_usage}/{structure.max_capacity}\n"
                        f"**Upkeep:** {structure.upkeep_cost:,} gold/week"
                    ),
                    inline=False
                )

            embed.set_footer(text="Use /structure_view <id> to see contents")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="structure_build", description="Build a new structure")
    @app_commands.guild_only()
    async def structure_build(self, interaction: discord.Interaction):
        """Build structure"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ Create your profile first with `/profile`",
                    ephemeral=True
                )
                return

            # Show available structures
            embed = discord.Embed(
                title="🏗️ Available Structures",
                description="Select a structure to build:",
                color=discord.Color.blue()
            )

            for struct_type, info in self.structure_info.items():
                embed.add_field(
                    name=f"{info['emoji']} {info['name']}",
                    value=(
                        f"{info['description']}\n"
                        f"**Capacity:** {info['capacity']} items\n"
                        f"**Cost:** {info['cost']:,} gold\n"
                        f"**Upkeep:** {info['upkeep']:,} gold/week"
                    ),
                    inline=True
                )

            embed.set_footer(text=f"Your gold: {profile.gold:,}")

            view = BuildStructureView(self, profile.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="structure_view", description="View structure contents")
    @app_commands.guild_only()
    @app_commands.describe(structure_id="Structure ID")
    async def structure_view(self, interaction: discord.Interaction, structure_id: int):
        """View structure contents"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ Create your profile first with `/profile`",
                    ephemeral=True
                )
                return

            structure = session.query(PlayerStructure).filter_by(
                id=structure_id,
                profile_id=profile.id
            ).first()

            if not structure:
                await interaction.response.send_message(
                    "❌ Structure not found or not yours.",
                    ephemeral=True
                )
                return

            stored = session.query(StructureStorage).filter_by(
                structure_id=structure_id
            ).all()

            info = self.structure_info[structure.structure_type]

            embed = discord.Embed(
                title=f"{info['emoji']} {info['name']}",
                description=f"**Capacity:** {structure.current_usage}/{structure.max_capacity}",
                color=discord.Color.green()
            )

            if stored:
                for storage in stored[:25]:
                    item = storage.item
                    embed.add_field(
                        name=f"{item.emoji or '•'} {item.name} x{storage.quantity}",
                        value=f"Item ID: {item.id}",
                        inline=True
                    )
            else:
                embed.description += "\n\n*Empty*"

            embed.set_footer(text="Use /store or /retrieve to manage items")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="store", description="Store items in a structure")
    @app_commands.guild_only()
    @app_commands.describe(
        structure_id="Structure ID",
        item_id="Item ID from inventory",
        quantity="Quantity to store"
    )
    async def store(
            self,
            interaction: discord.Interaction,
            structure_id: int,
            item_id: int,
            quantity: int = 1
    ):
        """Store items"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ Create your profile first with `/profile`",
                    ephemeral=True
                )
                return

            structure = session.query(PlayerStructure).filter_by(
                id=structure_id,
                profile_id=profile.id
            ).first()

            if not structure:
                await interaction.response.send_message(
                    "❌ Structure not found or not yours.",
                    ephemeral=True
                )
                return

            # Check inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=item_id
            ).first()

            if not inv_item or inv_item.quantity < quantity:
                await interaction.response.send_message(
                    "❌ You don't have enough of this item in your inventory!",
                    ephemeral=True
                )
                return

            # Check capacity
            if structure.current_usage + quantity > structure.max_capacity:
                await interaction.response.send_message(
                    f"❌ Not enough space! Structure has {structure.max_capacity - structure.current_usage} slots free.",
                    ephemeral=True
                )
                return

            # Move items
            inv_item.quantity -= quantity
            if inv_item.quantity <= 0:
                session.delete(inv_item)

            # Add to storage
            stored = session.query(StructureStorage).filter_by(
                structure_id=structure_id,
                item_id=item_id
            ).first()

            if stored:
                stored.quantity += quantity
            else:
                stored = StructureStorage(
                    structure_id=structure_id,
                    item_id=item_id,
                    quantity=quantity
                )
                session.add(stored)

            structure.current_usage += quantity
            session.commit()

            item = inv_item.item if inv_item else stored.item

        await interaction.response.send_message(
            f"✅ Stored {quantity}x **{item.name}** in your structure!",
            ephemeral=True
        )

    @app_commands.command(name="retrieve", description="Retrieve items from storage")
    @app_commands.guild_only()
    @app_commands.describe(
        structure_id="Structure ID",
        item_id="Item ID",
        quantity="Quantity to retrieve"
    )
    async def retrieve(
            self,
            interaction: discord.Interaction,
            structure_id: int,
            item_id: int,
            quantity: int = 1
    ):
        """Retrieve items"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ Create your profile first with `/profile`",
                    ephemeral=True
                )
                return

            structure = session.query(PlayerStructure).filter_by(
                id=structure_id,
                profile_id=profile.id
            ).first()

            if not structure:
                await interaction.response.send_message(
                    "❌ Structure not found or not yours.",
                    ephemeral=True
                )
                return

            # Check storage
            stored = session.query(StructureStorage).filter_by(
                structure_id=structure_id,
                item_id=item_id
            ).first()

            if not stored or stored.quantity < quantity:
                await interaction.response.send_message(
                    "❌ Not enough items in storage!",
                    ephemeral=True
                )
                return

            # Move items
            stored.quantity -= quantity
            if stored.quantity <= 0:
                session.delete(stored)

            # Add to inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=item_id
            ).first()

            if inv_item:
                inv_item.quantity += quantity
            else:
                inv_item = InventoryItem(
                    profile_id=profile.id,
                    item_id=item_id,
                    quantity=quantity
                )
                session.add(inv_item)

            structure.current_usage -= quantity
            session.commit()

            item = stored.item if stored else inv_item.item

        await interaction.response.send_message(
            f"✅ Retrieved {quantity}x **{item.name}** from storage!",
            ephemeral=True
        )

    async def build_structure_internal(self, profile_id: int, structure_type: StructureType):
        """Internal: Build a structure"""
        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(id=profile_id).first()

            info = self.structure_info[structure_type]

            # Check gold
            if profile.gold < info['cost']:
                return False, f"Not enough gold! Need {info['cost']:,}, you have {profile.gold:,}"

            # Deduct cost
            profile.gold -= info['cost']

            # Create structure
            structure = PlayerStructure(
                profile_id=profile_id,
                structure_type=structure_type,
                max_capacity=info['capacity'],
                build_cost=info['cost'],
                upkeep_cost=info['upkeep']
            )
            session.add(structure)
            session.commit()

            return True, f"Built {info['name']} for {info['cost']:,} gold!"

    def _create_bar(self, percentage: float, length: int = 10) -> str:
        """Create progress bar"""
        filled = int(length * percentage / 100)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}]"


class BuildStructureView(discord.ui.View):
    """Structure building UI"""

    def __init__(self, cog, profile_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.profile_id = profile_id

        # Create select options
        options = []
        for struct_type, info in cog.structure_info.items():
            options.append(
                discord.SelectOption(
                    label=info['name'],
                    value=struct_type.value,
                    description=f"{info['capacity']} slots - {info['cost']:,} gold",
                    emoji=info['emoji']
                )
            )

        select = discord.ui.Select(
            placeholder="Choose a structure to build...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        struct_type = StructureType(interaction.data['values'][0])

        success, message = await self.cog.build_structure_internal(self.profile_id, struct_type)

        if success:
            await interaction.response.send_message(
                f"✅ {message}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {message}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(StructuresCog(bot))