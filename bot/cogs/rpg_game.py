# File: cogs/rpg_game.py
# Location: /bot/cogs/rpg_game.py
import json

import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from models import Guild, Member
from models_rpg import (
    UserProfile, RPGItem, InventoryItem, EquippedItem, Enemy, BattleLog,
    DailyQuest, UserQuestProgress, Trade, Leaderboard,
    RPGItemRarity, RPGItemSlot
)
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class RPGGameCog(commands.Cog):
    """RPG mini-game with leveling, combat, and inventory"""

    def __init__(self, bot):
        self.bot = bot
        self.rarity_colors = {
            RPGItemRarity.COMMON: discord.Color.light_grey(),
            RPGItemRarity.UNCOMMON: discord.Color.green(),
            RPGItemRarity.RARE: discord.Color.blue(),
            RPGItemRarity.EPIC: discord.Color.purple(),
            RPGItemRarity.LEGENDARY: discord.Color.orange(),
            RPGItemRarity.MYTHIC: discord.Color.red()
        }

    @app_commands.command(name="profile", description="View your RPG profile")
    @app_commands.guild_only()
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        """View RPG profile"""
        target = member or interaction.user

        profile = await self._get_or_create_profile(interaction.guild.id, target.id, target.name)

        if not profile:
            await interaction.response.send_message("❌ Profile not found.", ephemeral=True)
            return

        # Calculate total stats with equipment
        total_attack, total_defense, total_health, total_luck = await self._calculate_stats(profile.id)

        embed = discord.Embed(
            title=f"⚔️ {target.display_name}'s Profile",
            color=discord.Color.gold()
        )

        embed.set_thumbnail(url=target.display_avatar.url)

        # Level and Experience
        exp_progress = f"{profile.experience}/{profile.next_level_exp}"
        exp_percentage = int((profile.experience / profile.next_level_exp) * 100)
        exp_bar = self._create_progress_bar(exp_percentage)

        embed.add_field(
            name="📊 Level & Experience",
            value=f"**Level:** {profile.level}\n**EXP:** {exp_progress}\n{exp_bar}",
            inline=False
        )

        # Stats
        embed.add_field(
            name="💪 Stats",
            value=(
                f"**HP:** {profile.current_health}/{total_health}\n"
                f"**Attack:** {total_attack}\n"
                f"**Defense:** {total_defense}\n"
                f"**Luck:** {total_luck}"
            ),
            inline=True
        )

        # Currency
        embed.add_field(
            name="💰 Currency",
            value=f"**Gold:** {profile.gold:,}\n**Gems:** {profile.gems:,}",
            inline=True
        )

        # Combat Stats
        win_rate = (profile.battles_won / profile.total_battles * 100) if profile.total_battles > 0 else 0
        embed.add_field(
            name="⚔️ Combat Record",
            value=(
                f"**Battles:** {profile.total_battles}\n"
                f"**Wins:** {profile.battles_won}\n"
                f"**Win Rate:** {win_rate:.1f}%"
            ),
            inline=True
        )

        embed.set_footer(text=f"Joined: {profile.created_at.strftime('%Y-%m-%d')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="battle", description="Battle an enemy!")
    @app_commands.guild_only()
    async def battle(self, interaction: discord.Interaction, enemy_id: Optional[int] = None):
        """Start a battle"""
        profile = await self._get_or_create_profile(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        # Check cooldown
        if profile.last_battle:
            time_since = datetime.utcnow() - profile.last_battle
            if time_since < timedelta(minutes=5):
                remaining = 5 - int(time_since.total_seconds() / 60)
                await interaction.response.send_message(
                    f"⏱️ You're exhausted! Wait {remaining} more minute(s) before battling again.",
                    ephemeral=True
                )
                return

        # Check health
        if profile.current_health <= 0:
            await interaction.response.send_message(
                "💀 You're defeated! Use a health potion or wait for health to regenerate.",
                ephemeral=True
            )
            return

        with db.session_scope() as session:
            if enemy_id:
                enemy = session.query(Enemy).filter_by(id=enemy_id).first()
            else:
                # Random enemy based on player level
                min_level = max(1, profile.level - 2)
                max_level = profile.level + 2
                enemy = session.query(Enemy).filter(
                    Enemy.level >= min_level,
                    Enemy.level <= max_level
                ).order_by(db.engine.dialect.name == 'postgresql' and 'RANDOM()' or text('RANDOM()')).first()

            if not enemy:
                await interaction.response.send_message("❌ No suitable enemies found!", ephemeral=True)
                return

            view = BattleView(self, profile.id, enemy.id)
            embed = await self._create_battle_start_embed(profile, enemy)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="inventory", description="View your inventory")
    @app_commands.guild_only()
    async def inventory(self, interaction: discord.Interaction):
        """View inventory"""
        profile = await self._get_or_create_profile(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            inventory = session.query(InventoryItem).filter_by(
                profile_id=profile.id
            ).all()

            if not inventory:
                await interaction.response.send_message(
                    "📦 Your inventory is empty! Battle enemies to find loot.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"🎒 {interaction.user.display_name}'s Inventory",
                color=discord.Color.blue()
            )

            # Group by slot
            by_slot = {}
            for inv_item in inventory:
                item = inv_item.item
                slot = item.slot.value
                if slot not in by_slot:
                    by_slot[slot] = []
                by_slot[slot].append((inv_item, item))

            for slot, items in by_slot.items():
                items_text = []
                for inv_item, item in items[:10]:
                    emoji = item.emoji or "•"
                    rarity_emoji = self._get_rarity_emoji(item.rarity)
                    qty = f"x{inv_item.quantity}" if inv_item.quantity > 1 else ""
                    items_text.append(f"{emoji} {item.name} {rarity_emoji} {qty} (ID: {item.id})")

                embed.add_field(
                    name=f"{slot.title()} ({len(items)})",
                    value="\n".join(items_text) if items_text else "Empty",
                    inline=False
                )

            embed.set_footer(text="Use /equip <item_id> to equip items")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="equip", description="Equip an item from your inventory")
    @app_commands.guild_only()
    @app_commands.describe(item_id="Item ID from your inventory")
    async def equip(self, interaction: discord.Interaction, item_id: int):
        """Equip item"""
        profile = await self._get_or_create_profile(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        with db.session_scope() as session:
            # Check if player owns the item
            inv_item = session.query(InventoryItem).filter_by(
                profile_id=profile.id,
                item_id=item_id
            ).first()

            if not inv_item:
                await interaction.response.send_message("❌ You don't own this item.", ephemeral=True)
                return

            item = inv_item.item

            # Check level requirement
            if item.level_required > profile.level:
                await interaction.response.send_message(
                    f"❌ You need to be level {item.level_required} to equip this item.",
                    ephemeral=True
                )
                return

            # Unequip current item in slot
            current = session.query(EquippedItem).filter_by(
                profile_id=profile.id,
                slot=item.slot
            ).first()

            if current:
                session.delete(current)

            # Equip new item
            equipped = EquippedItem(
                profile_id=profile.id,
                item_id=item_id,
                slot=item.slot
            )
            session.add(equipped)
            session.commit()

        await interaction.response.send_message(
            f"✅ Equipped **{item.name}**!",
            ephemeral=True
        )

    @app_commands.command(name="unequip", description="Unequip an item")
    @app_commands.guild_only()
    @app_commands.describe(slot="Slot to unequip (weapon, chest, etc.)")
    async def unequip(self, interaction: discord.Interaction, slot: str):
        """Unequip item"""
        profile = await self._get_or_create_profile(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        try:
            slot_enum = RPGItemSlot(slot.lower())
        except ValueError:
            await interaction.response.send_message("❌ Invalid slot.", ephemeral=True)
            return

        with db.session_scope() as session:
            equipped = session.query(EquippedItem).filter_by(
                profile_id=profile.id,
                slot=slot_enum
            ).first()

            if not equipped:
                await interaction.response.send_message(
                    f"❌ No item equipped in {slot} slot.",
                    ephemeral=True
                )
                return

            item_name = equipped.item.name
            session.delete(equipped)
            session.commit()

        await interaction.response.send_message(
            f"✅ Unequipped **{item_name}**",
            ephemeral=True
        )

    @app_commands.command(name="daily", description="Claim your daily rewards")
    @app_commands.guild_only()
    async def daily(self, interaction: discord.Interaction):
        """Daily rewards"""
        profile = await self._get_or_create_profile(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.name
        )

        # Check if already claimed today
        if profile.last_daily_claim:
            time_since = datetime.utcnow() - profile.last_daily_claim
            if time_since < timedelta(days=1):
                hours_left = 24 - int(time_since.total_seconds() / 3600)
                await interaction.response.send_message(
                    f"⏱️ Daily reward already claimed! Come back in {hours_left} hours.",
                    ephemeral=True
                )
                return

        # Give rewards
        gold_reward = random.randint(50, 150)
        exp_reward = random.randint(25, 75)

        with db.session_scope() as session:
            prof = session.query(UserProfile).filter_by(id=profile.id).first()
            prof.gold += gold_reward
            prof.experience += exp_reward
            prof.last_daily_claim = datetime.utcnow()

            # Check for level up
            if prof.experience >= prof.next_level_exp:
                prof.level += 1
                prof.experience -= prof.next_level_exp
                prof.next_level_exp = int(prof.next_level_exp * 1.5)
                prof.max_health += 10
                prof.current_health = prof.max_health
                prof.attack += 2
                prof.defense += 1
                leveled_up = True
            else:
                leveled_up = False

            session.commit()

        embed = discord.Embed(
            title="🎁 Daily Rewards",
            description="You've claimed your daily rewards!",
            color=discord.Color.green()
        )

        embed.add_field(name="💰 Gold", value=f"+{gold_reward:,}", inline=True)
        embed.add_field(name="⭐ EXP", value=f"+{exp_reward}", inline=True)

        if leveled_up:
            embed.add_field(
                name="🎉 LEVEL UP!",
                value=f"You're now level {prof.level}!",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="leaderboard", description="View server leaderboard")
    @app_commands.guild_only()
    @app_commands.describe(category="Category to view (level, gold, battles)")
    async def leaderboard(self, interaction: discord.Interaction, category: str = "level"):
        """View leaderboard"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=interaction.guild.id).first()

            # Get all profiles for this guild
            profiles = session.query(UserProfile).join(Member).filter(
                Member.guild_id == guild.id
            ).all()

            if not profiles:
                await interaction.response.send_message(
                    "📊 No one has started their journey yet!",
                    ephemeral=True
                )
                return

            # Sort based on category
            if category == "level":
                profiles.sort(key=lambda p: (p.level, p.experience), reverse=True)
                title = "📊 Level Leaderboard"
                value_format = lambda p: f"Level {p.level} ({p.experience:,} EXP)"
            elif category == "gold":
                profiles.sort(key=lambda p: p.gold, reverse=True)
                title = "💰 Wealth Leaderboard"
                value_format = lambda p: f"{p.gold:,} gold"
            elif category == "battles":
                profiles.sort(key=lambda p: p.battles_won, reverse=True)
                title = "⚔️ Battle Leaderboard"
                value_format = lambda p: f"{p.battles_won} wins"
            else:
                await interaction.response.send_message("❌ Invalid category.", ephemeral=True)
                return

            embed = discord.Embed(
                title=title,
                color=discord.Color.gold()
            )

            leaderboard_text = []
            for i, profile in enumerate(profiles[:10], 1):
                user_id = profile.member.user_id
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text.append(f"{medal} <@{user_id}> - {value_format(profile)}")

            embed.description = "\n".join(leaderboard_text)
            embed.set_footer(text=f"Showing top {min(10, len(profiles))} players")

            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _get_or_create_profile(self, guild_id: int, user_id: int, username: str):
        """Get or create RPG profile"""
        from utils.helpers import get_or_create_member

        member = await get_or_create_member(guild_id, user_id, username)

        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                profile = UserProfile(member_id=member.id)
                session.add(profile)
                session.commit()
                session.refresh(profile)

            return profile

    async def _calculate_stats(self, profile_id: int):
        """Calculate total stats with equipment bonuses"""
        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(id=profile_id).first()

            total_attack = profile.attack
            total_defense = profile.defense
            total_health = profile.max_health
            total_luck = profile.luck

            # Add equipment bonuses
            equipped = session.query(EquippedItem).filter_by(profile_id=profile_id).all()

            for eq in equipped:
                item = eq.item
                total_attack += item.attack_bonus
                total_defense += item.defense_bonus
                total_health += item.health_bonus
                total_luck += item.luck_bonus

            return total_attack, total_defense, total_health, total_luck

    async def _create_battle_start_embed(self, profile, enemy):
        """Create battle start embed"""
        total_attack, total_defense, total_health, total_luck = await self._calculate_stats(profile.id)

        embed = discord.Embed(
            title=f"⚔️ Battle Started!",
            description=f"You've encountered a {enemy.emoji} **{enemy.name}**!",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Your Stats",
            value=f"❤️ HP: {profile.current_health}/{total_health}\n⚔️ ATK: {total_attack}\n🛡️ DEF: {total_defense}",
            inline=True
        )

        embed.add_field(
            name="Enemy Stats",
            value=f"❤️ HP: {enemy.health}\n⚔️ ATK: {enemy.attack}\n🛡️ DEF: {enemy.defense}",
            inline=True
        )

        embed.set_footer(text="Click 'Attack' to fight or 'Flee' to escape!")

        return embed

    def _create_progress_bar(self, percentage: int, length: int = 10) -> str:
        """Create a progress bar"""
        filled = int(length * percentage / 100)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}] {percentage}%"

    def _get_rarity_emoji(self, rarity: RPGItemRarity) -> str:
        """Get emoji for rarity"""
        emojis = {
            RPGItemRarity.COMMON: "⚪",
            RPGItemRarity.UNCOMMON: "🟢",
            RPGItemRarity.RARE: "🔵",
            RPGItemRarity.EPIC: "🟣",
            RPGItemRarity.LEGENDARY: "🟠",
            RPGItemRarity.MYTHIC: "🔴"
        }
        return emojis.get(rarity, "⚪")


class BattleView(discord.ui.View):
    """Battle UI"""

    def __init__(self, cog, profile_id: int, enemy_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.profile_id = profile_id
        self.enemy_id = enemy_id

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Execute battle"""
        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(id=self.profile_id).first()
            enemy = session.query(Enemy).filter_by(id=self.enemy_id).first()

            # Calculate stats
            p_attack, p_defense, p_max_health, p_luck = await self.cog._calculate_stats(self.profile_id)

            # Battle simulation
            player_hp = profile.current_health
            enemy_hp = enemy.health

            rounds = []
            while player_hp > 0 and enemy_hp > 0:
                # Player attacks
                damage = max(1, p_attack - enemy.defense + random.randint(-5, 5))
                enemy_hp -= damage
                rounds.append(f"You deal **{damage}** damage!")

                if enemy_hp <= 0:
                    break

                # Enemy attacks
                damage = max(1, enemy.attack - p_defense + random.randint(-3, 3))
                player_hp -= damage
                rounds.append(f"{enemy.name} deals **{damage}** damage!")

            won = enemy_hp <= 0

            # Calculate rewards
            exp_gained = enemy.exp_reward
            gold_gained = random.randint(enemy.gold_min, enemy.gold_max)
            loot = []

            if won and enemy.loot_table:
                for loot_entry in json.loads(enemy.loot_table):
                    if random.random() < loot_entry.get('chance', 0):
                        loot.append(loot_entry['item_id'])

            # Update profile
            profile.current_health = max(0, player_hp)
            profile.total_battles += 1
            profile.last_battle = datetime.utcnow()

            if won:
                profile.battles_won += 1
                profile.experience += exp_gained
                profile.gold += gold_gained

                # Check level up
                leveled_up = False
                if profile.experience >= profile.next_level_exp:
                    profile.level += 1
                    profile.experience -= profile.next_level_exp
                    profile.next_level_exp = int(profile.next_level_exp * 1.5)
                    profile.max_health += 10
                    profile.current_health = profile.max_health
                    profile.attack += 2
                    profile.defense += 1
                    leveled_up = True

                # Add loot to inventory
                for item_id in loot:
                    inv_item = session.query(InventoryItem).filter_by(
                        profile_id=profile.id,
                        item_id=item_id
                    ).first()

                    if inv_item:
                        inv_item.quantity += 1
                    else:
                        inv_item = InventoryItem(
                            profile_id=profile.id,
                            item_id=item_id,
                            quantity=1
                        )
                        session.add(inv_item)

            # Log battle
            battle_log = BattleLog(
                profile_id=profile.id,
                enemy_id=enemy.id,
                won=won,
                damage_dealt=enemy.health - max(0, enemy_hp),
                damage_taken=profile.current_health - player_hp,
                exp_gained=exp_gained if won else 0,
                gold_gained=gold_gained if won else 0,
                loot_gained=loot if loot else None
            )
            session.add(battle_log)

            session.commit()

        # Create result embed
        if won:
            embed = discord.Embed(
                title="🎉 Victory!",
                description=f"You defeated the {enemy.name}!",
                color=discord.Color.green()
            )

            embed.add_field(name="⭐ EXP", value=f"+{exp_gained}", inline=True)
            embed.add_field(name="💰 Gold", value=f"+{gold_gained:,}", inline=True)
            embed.add_field(name="❤️ HP Remaining", value=f"{max(0, player_hp)}/{p_max_health}", inline=True)

            if loot:
                loot_items = session.query(RPGItem).filter(RPGItem.id.in_(loot)).all()
                loot_text = "\n".join([f"• {item.emoji} {item.name}" for item in loot_items])
                embed.add_field(name="🎁 Loot", value=loot_text, inline=False)

            if leveled_up:
                embed.add_field(
                    name="🎉 LEVEL UP!",
                    value=f"You're now level {profile.level}!",
                    inline=False
                )
        else:
            embed = discord.Embed(
                title="💀 Defeated...",
                description=f"You were defeated by the {enemy.name}.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="💭 What now?",
                value="Use health potions to recover, or wait for natural regeneration.",
                inline=False
            )

        # Show a few battle rounds
        if len(rounds) > 6:
            rounds = rounds[:3] + ["..."] + rounds[-3:]

        embed.add_field(
            name="⚔️ Battle Log",
            value="\n".join(rounds),
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Flee from battle"""
        with db.session_scope() as session:
            profile = session.query(UserProfile).filter_by(id=self.profile_id).first()
            profile.last_battle = datetime.utcnow()
            session.commit()

        embed = discord.Embed(
            title="🏃 Fled!",
            description="You escaped from battle!",
            color=discord.Color.light_grey()
        )

        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(RPGGameCog(bot))