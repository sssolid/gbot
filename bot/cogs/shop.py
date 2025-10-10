# File: cogs/shop.py
# Location: /bot/cogs/shop.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime, timedelta

from models import Guild
from models_rpg import UserProfile, RPGItem, InventoryItem
from models_rpg import ShopItem, PlayerMarketListing, TransactionLog
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """NPC shop and player marketplace"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Browse the NPC shop")
    @app_commands.guild_only()
    async def shop(self, interaction: discord.Interaction):
        """View shop"""
        with db.session_scope() as session:
            items = session.query(ShopItem).filter_by(is_available=True).limit(20).all()

            if not items:
                await interaction.response.send_message(
                    "🏪 The shop is currently empty! Come back later.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🏪 General Store",
                description="Buy items with gold. Use `/buy <id>` to purchase.",
                color=discord.Color.gold()
            )

            for shop_item in items:
                item = shop_item.item

                stock_text = f"Stock: {shop_item.stock}" if shop_item.stock >= 0 else "Unlimited"

                embed.add_field(
                    name=f"{item.emoji or '•'} {item.name}",
                    value=(
                        f"**Price:** {shop_item.buy_price:,} gold\n"
                        f"**Level:** {shop_item.requires_level}+\n"
                        f"{stock_text}\n"
                        f"ID: {shop_item.id}"
                    ),
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.guild_only()
    @app_commands.describe(
        item_id="Shop item ID",
        quantity="Quantity to buy"
    )
    async def buy(self, interaction: discord.Interaction, item_id: int, quantity: int = 1):
        """Buy from NPC shop"""
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

            shop_item = session.query(ShopItem).filter_by(id=item_id).first()

            if not shop_item or not shop_item.is_available:
                await interaction.response.send_message(
                    "❌ Item not found or not available.",
                    ephemeral=True
                )
                return

            # Check level
            if profile.level < shop_item.requires_level:
                await interaction.response.send_message(
                    f"❌ You need to be level {shop_item.requires_level} to buy this item.",
                    ephemeral=True
                )
                return

            # Check stock
            if shop_item.stock >= 0 and shop_item.stock < quantity:
                await interaction.response.send_message(
                    f"❌ Not enough stock! Only {shop_item.stock} available.",
                    ephemeral=True
                )
                return

            # Check gold
            total_cost = shop_item.buy_price * quantity
            if profile.gold < total_cost:
                await interaction.response.send_message(
                    f"❌ Not enough gold! Need {total_cost:,}, you have {profile.gold:,}",
                    ephemeral=True
                )
                return

            # Process purchase
            profile.gold -= total_cost

            if shop_item.stock >= 0:
                shop_item.stock -= quantity

            # Add to inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=shop_item.item_id
            ).first()

            if inv_item:
                inv_item.quantity += quantity
            else:
                inv_item = InventoryItem(
                    profile_id=profile.id,
                    item_id=shop_item.item_id,
                    quantity=quantity
                )
                session.add(inv_item)

            # Log transaction
            transaction = TransactionLog(
                buyer_profile_id=profile.id,
                item_id=shop_item.item_id,
                quantity=quantity,
                price_paid=total_cost,
                transaction_type='npc_shop'
            )
            session.add(transaction)

            session.commit()

            item = shop_item.item

        await interaction.response.send_message(
            f"✅ Purchased {quantity}x **{item.name}** for {total_cost:,} gold!\n"
            f"💰 Remaining gold: {profile.gold:,}",
            ephemeral=True
        )

    @app_commands.command(name="sell", description="Sell an item to the shop")
    @app_commands.guild_only()
    @app_commands.describe(
        item_id="Item ID from your inventory",
        quantity="Quantity to sell"
    )
    async def sell(self, interaction: discord.Interaction, item_id: int, quantity: int = 1):
        """Sell to NPC shop"""
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

            # Check inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=item_id
            ).first()

            if not inv_item or inv_item.quantity < quantity:
                await interaction.response.send_message(
                    "❌ You don't have enough of this item!",
                    ephemeral=True
                )
                return

            item = inv_item.item

            # Calculate sell price (50% of buy price)
            sell_price = max(1, item.sell_price * quantity)

            # Process sale
            profile.gold += sell_price
            inv_item.quantity -= quantity

            if inv_item.quantity <= 0:
                session.delete(inv_item)

            # Log transaction
            transaction = TransactionLog(
                seller_profile_id=profile.id,
                buyer_profile_id=profile.id,  # Selling to NPC
                item_id=item_id,
                quantity=quantity,
                price_paid=sell_price,
                transaction_type='npc_shop'
            )
            session.add(transaction)

            session.commit()

        await interaction.response.send_message(
            f"✅ Sold {quantity}x **{item.name}** for {sell_price:,} gold!\n"
            f"💰 New balance: {profile.gold:,}",
            ephemeral=True
        )

    @app_commands.command(name="market_list", description="List an item on the player marketplace")
    @app_commands.guild_only()
    @app_commands.describe(
        item_id="Item ID from inventory",
        price="Price per item in gold",
        quantity="Quantity to list"
    )
    async def market_list(
            self,
            interaction: discord.Interaction,
            item_id: int,
            price: int,
            quantity: int = 1
    ):
        """List item on marketplace"""
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

            # Check inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=item_id
            ).first()

            if not inv_item or inv_item.quantity < quantity:
                await interaction.response.send_message(
                    "❌ You don't have enough of this item!",
                    ephemeral=True
                )
                return

            item = inv_item.item

            # Remove from inventory temporarily
            inv_item.quantity -= quantity
            if inv_item.quantity <= 0:
                session.delete(inv_item)

            # Create listing
            listing = PlayerMarketListing(
                seller_profile_id=profile.id,
                item_id=item_id,
                quantity=quantity,
                price_per_item=price,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            session.add(listing)
            session.commit()

        total_value = price * quantity
        await interaction.response.send_message(
            f"✅ Listed {quantity}x **{item.name}** for {price:,} gold each (Total: {total_value:,} gold)\n"
            "Listing expires in 7 days.",
            ephemeral=True
        )

    @app_commands.command(name="market", description="Browse the player marketplace")
    @app_commands.guild_only()
    @app_commands.describe(search="Search for items")
    async def market(self, interaction: discord.Interaction, search: str = None):
        """Browse marketplace"""
        with db.session_scope() as session:
            query = session.query(PlayerMarketListing).filter_by(is_active=True)

            if search:
                query = query.join(RPGItem).filter(RPGItem.name.ilike(f"%{search}%"))

            listings = query.order_by(PlayerMarketListing.listed_at.desc()).limit(10).all()

            if not listings:
                await interaction.response.send_message(
                    "🏛️ No items currently listed on the marketplace.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🏛️ Player Marketplace",
                description="Buy from other players. Use `/market_buy <id>` to purchase.",
                color=discord.Color.blue()
            )

            for listing in listings:
                item = listing.item
                seller = listing.seller

                total_price = listing.price_per_item * listing.quantity

                embed.add_field(
                    name=f"{item.emoji or '•'} {item.name} x{listing.quantity}",
                    value=(
                        f"**Price:** {listing.price_per_item:,} each ({total_price:,} total)\n"
                        f"**Seller:** <@{seller.member.user_id}>\n"
                        f"ID: {listing.id}"
                    ),
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="market_buy", description="Buy from the marketplace")
    @app_commands.guild_only()
    @app_commands.describe(listing_id="Listing ID")
    async def market_buy(self, interaction: discord.Interaction, listing_id: int):
        """Buy from marketplace"""
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

            listing = session.query(PlayerMarketListing).filter_by(
                id=listing_id,
                is_active=True
            ).first()

            if not listing:
                await interaction.response.send_message(
                    "❌ Listing not found or expired.",
                    ephemeral=True
                )
                return

            # Can't buy own listing
            if listing.seller_profile_id == profile.id:
                await interaction.response.send_message(
                    "❌ You can't buy your own listing!",
                    ephemeral=True
                )
                return

            total_cost = listing.price_per_item * listing.quantity

            # Check gold
            if profile.gold < total_cost:
                await interaction.response.send_message(
                    f"❌ Not enough gold! Need {total_cost:,}, you have {profile.gold:,}",
                    ephemeral=True
                )
                return

            # Process purchase
            profile.gold -= total_cost
            listing.seller.gold += total_cost

            # Add to buyer's inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=listing.item_id
            ).first()

            if inv_item:
                inv_item.quantity += listing.quantity
            else:
                inv_item = InventoryItem(
                    profile_id=profile.id,
                    item_id=listing.item_id,
                    quantity=listing.quantity
                )
                session.add(inv_item)

            # Complete listing
            listing.is_active = False
            listing.buyer_profile_id = profile.id
            listing.sold_at = datetime.utcnow()

            # Log transaction
            transaction = TransactionLog(
                seller_profile_id=listing.seller_profile_id,
                buyer_profile_id=profile.id,
                item_id=listing.item_id,
                quantity=listing.quantity,
                price_paid=total_cost,
                transaction_type='player_market'
            )
            session.add(transaction)

            session.commit()

            item = listing.item

        await interaction.response.send_message(
            f"✅ Purchased {listing.quantity}x **{item.name}** for {total_cost:,} gold!\n"
            f"💰 Remaining gold: {profile.gold:,}",
            ephemeral=True
        )

    @app_commands.command(name="market_cancel", description="Cancel your marketplace listing")
    @app_commands.guild_only()
    @app_commands.describe(listing_id="Listing ID")
    async def market_cancel(self, interaction: discord.Interaction, listing_id: int):
        """Cancel listing"""
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

            listing = session.query(PlayerMarketListing).filter_by(
                id=listing_id,
                seller_profile_id=profile.id,
                is_active=True
            ).first()

            if not listing:
                await interaction.response.send_message(
                    "❌ Listing not found or not yours.",
                    ephemeral=True
                )
                return

            # Return items to inventory
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=listing.item_id
            ).first()

            if inv_item:
                inv_item.quantity += listing.quantity
            else:
                inv_item = InventoryItem(
                    profile_id=profile.id,
                    item_id=listing.item_id,
                    quantity=listing.quantity
                )
                session.add(inv_item)

            listing.is_active = False
            session.commit()

            item = listing.item

        await interaction.response.send_message(
            f"✅ Cancelled listing for {listing.quantity}x **{item.name}**\n"
            "Items returned to your inventory.",
            ephemeral=True
        )

    @app_commands.command(name="shop_add", description="Add item to shop (Admin)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        item_id="RPG item ID",
        price="Buy price",
        stock="Stock (-1 for unlimited)"
    )
    async def shop_add(
            self,
            interaction: discord.Interaction,
            item_id: int,
            price: int,
            stock: int = -1
    ):
        """Add item to NPC shop"""
        with db.session_scope() as session:
            item = session.query(RPGItem).filter_by(id=item_id).first()

            if not item:
                await interaction.response.send_message(
                    "❌ Item not found.",
                    ephemeral=True
                )
                return

            shop_item = ShopItem(
                item_id=item_id,
                buy_price=price,
                stock=stock
            )
            session.add(shop_item)
            session.commit()

        await interaction.response.send_message(
            f"✅ Added **{item.name}** to shop for {price:,} gold",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ShopCog(bot))