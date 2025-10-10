# File: cogs/raids.py
# Location: /bot/cogs/raids.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from models import Guild, Member
from models_rpg import UserProfile, RPGItem, Enemy
from models_rpg import (
    Raid, RaidWave, RaidParticipant, RaidLoot, LootRoll,
    RaidStatus, RaidDifficulty, RollType
)
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class RaidsCog(commands.Cog):
    """Collaborative raid battles with wave-based combat"""

    def __init__(self, bot):
        self.bot = bot
        self.active_raids = {}  # guild_id -> raid_id
        self.check_raids.start()
        self.process_loot_rolls.start()

    def cog_unload(self):
        self.check_raids.cancel()
        self.process_loot_rolls.cancel()

    @app_commands.command(name="raid_start", description="Start a raid event (Admin)")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        difficulty="Raid difficulty",
        min_level="Minimum player level"
    )
    async def raid_start(
            self,
            interaction: discord.Interaction,
            difficulty: str = "normal",
            min_level: int = 5
    ):
        """Start a raid event"""
        if interaction.guild.id in self.active_raids:
            await interaction.response.send_message(
                "❌ A raid is already active! Use `/raid_join` to participate.",
                ephemeral=True
            )
            return

        try:
            diff_enum = RaidDifficulty(difficulty.lower())
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid difficulty. Use: easy, normal, hard, or nightmare",
                ephemeral=True
            )
            return

        # Create raid
        raid = await self._create_raid(
            interaction.guild.id,
            diff_enum,
            min_level
        )

        if not raid:
            await interaction.response.send_message(
                "❌ Failed to create raid. Make sure enemies exist in the database.",
                ephemeral=True
            )
            return

        self.active_raids[interaction.guild.id] = raid.id

        # Create announcement embed
        embed = await self._create_raid_announcement(raid)

        # Send to channel
        message = await interaction.channel.send(
            content="@here 🚨 **RAID ALERT!** 🚨",
            embed=embed
        )

        # Update raid with message info
        with db.session_scope() as session:
            r = session.query(Raid).filter_by(id=raid.id).first()
            r.message_id = message.id
            r.channel_id = interaction.channel.id
            session.commit()

        await interaction.response.send_message(
            "✅ Raid started! Players have 2 minutes to join.",
            ephemeral=True
        )

        # Wait 2 minutes then start
        await asyncio.sleep(120)
        await self._start_raid_combat(interaction.guild.id, raid.id)

    @app_commands.command(name="raid_join", description="Join the active raid")
    @app_commands.guild_only()
    async def raid_join(self, interaction: discord.Interaction):
        """Join active raid"""
        if interaction.guild.id not in self.active_raids:
            await interaction.response.send_message(
                "❌ No active raid. Wait for the next one!",
                ephemeral=True
            )
            return

        raid_id = self.active_raids[interaction.guild.id]

        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()

            if raid.status != RaidStatus.WAITING:
                await interaction.response.send_message(
                    "❌ Raid already started! Wait for the next one.",
                    ephemeral=True
                )
                return

            # Get player profile
            from utils.helpers import get_or_create_member
            member = await get_or_create_member(
                interaction.guild.id,
                interaction.user.id,
                interaction.user.name
            )

            profile = session.query(UserProfile).filter_by(member_id=member.id).first()
            if not profile:
                await interaction.response.send_message(
                    "❌ You need to start your adventure first! Use `/profile`",
                    ephemeral=True
                )
                return

            # Check level requirement
            if profile.level < raid.min_level:
                await interaction.response.send_message(
                    f"❌ You need to be level {raid.min_level} or higher to join this raid.",
                    ephemeral=True
                )
                return

            # Check if already joined
            existing = session.query(RaidParticipant).filter_by(
                raid_id=raid_id,
                profile_id=profile.id
            ).first()

            if existing:
                await interaction.response.send_message(
                    "❌ You've already joined this raid!",
                    ephemeral=True
                )
                return

            # Check max players
            participant_count = session.query(RaidParticipant).filter_by(
                raid_id=raid_id
            ).count()

            if participant_count >= raid.max_players:
                await interaction.response.send_message(
                    "❌ Raid is full!",
                    ephemeral=True
                )
                return

            # Join raid
            participant = RaidParticipant(
                raid_id=raid_id,
                profile_id=profile.id
            )
            session.add(participant)
            session.commit()

        await interaction.response.send_message(
            "⚔️ You've joined the raid! Prepare for battle!",
            ephemeral=True
        )

        # Update raid message
        await self._update_raid_message(raid_id)

    @app_commands.command(name="raid_status", description="View current raid status")
    @app_commands.guild_only()
    async def raid_status(self, interaction: discord.Interaction):
        """View raid status"""
        if interaction.guild.id not in self.active_raids:
            await interaction.response.send_message(
                "❌ No active raid.",
                ephemeral=True
            )
            return

        raid_id = self.active_raids[interaction.guild.id]

        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()
            participants = session.query(RaidParticipant).filter_by(raid_id=raid_id).all()

            embed = discord.Embed(
                title=f"⚔️ {raid.name}",
                description=raid.description,
                color=discord.Color.red()
            )

            # Status
            status_text = f"**Status:** {raid.status.value.title()}\n"
            status_text += f"**Wave:** {raid.current_wave}/{raid.max_waves}\n"
            status_text += f"**Difficulty:** {raid.difficulty.value.title()}"
            embed.add_field(name="📊 Raid Info", value=status_text, inline=True)

            # Participants
            alive = sum(1 for p in participants if p.is_alive)
            total = len(participants)

            participant_list = []
            for p in sorted(participants, key=lambda x: x.damage_dealt, reverse=True)[:5]:
                status = "💀" if not p.is_alive else "⚔️"
                participant_list.append(f"{status} <@{p.profile.member.user_id}> - {p.damage_dealt:,} dmg")

            embed.add_field(
                name=f"👥 Participants ({alive}/{total})",
                value="\n".join(participant_list) if participant_list else "None",
                inline=True
            )

            # Current wave
            current_wave = session.query(RaidWave).filter_by(
                raid_id=raid_id,
                wave_number=raid.current_wave
            ).first()

            if current_wave and not current_wave.completed:
                health_pct = (current_wave.remaining_health / current_wave.total_enemy_health) * 100
                health_bar = self._create_health_bar(health_pct)

                embed.add_field(
                    name=f"🌊 Wave {raid.current_wave}",
                    value=f"{health_bar}\n{current_wave.remaining_health:,} / {current_wave.total_enemy_health:,} HP",
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _create_raid(
            self,
            guild_id: int,
            difficulty: RaidDifficulty,
            min_level: int
    ):
        """Create a new raid"""
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=guild_id).first()

            # Difficulty multipliers
            multipliers = {
                RaidDifficulty.EASY: 0.7,
                RaidDifficulty.NORMAL: 1.0,
                RaidDifficulty.HARD: 1.5,
                RaidDifficulty.NIGHTMARE: 2.5
            }
            mult = multipliers[difficulty]

            # Get random enemies
            enemies = session.query(Enemy).filter(
                Enemy.level >= min_level,
                Enemy.level <= min_level + 5
            ).all()

            if not enemies or len(enemies) < 3:
                return None

            # Create raid
            raid = Raid(
                guild_id=guild.id,
                name=f"{difficulty.value.title()} Raid",
                description="Defeat waves of enemies to claim rewards!",
                difficulty=difficulty,
                min_level=min_level,
                max_waves=3,
                ends_at=datetime.utcnow() + timedelta(minutes=30)
            )
            session.add(raid)
            session.flush()

            # Create waves
            # Wave 1: Multiple weak enemies
            wave1_enemy = random.choice([e for e in enemies if not e.name.lower().__contains__('dragon')])
            wave1 = RaidWave(
                raid_id=raid.id,
                wave_number=1,
                enemies=[{"enemy_id": wave1_enemy.id, "count": int(5 * mult)}],
                total_enemy_health=int(wave1_enemy.health * 5 * mult),
                remaining_health=int(wave1_enemy.health * 5 * mult)
            )
            session.add(wave1)

            # Wave 2: Fewer stronger enemies
            wave2_enemy = random.choice(enemies)
            wave2 = RaidWave(
                raid_id=raid.id,
                wave_number=2,
                enemies=[{"enemy_id": wave2_enemy.id, "count": int(3 * mult)}],
                total_enemy_health=int(wave2_enemy.health * 3 * mult * 1.5),
                remaining_health=int(wave2_enemy.health * 3 * mult * 1.5)
            )
            session.add(wave2)

            # Wave 3: Boss
            boss_enemy = max(enemies, key=lambda e: e.level)
            wave3 = RaidWave(
                raid_id=raid.id,
                wave_number=3,
                is_boss=True,
                enemies=[{"enemy_id": boss_enemy.id, "count": 1}],
                total_enemy_health=int(boss_enemy.health * 10 * mult),
                remaining_health=int(boss_enemy.health * 10 * mult)
            )
            session.add(wave3)

            session.commit()
            session.refresh(raid)

            return raid

    async def _create_raid_announcement(self, raid):
        """Create raid announcement embed"""
        embed = discord.Embed(
            title=f"🚨 {raid.name} 🚨",
            description=(
                f"{raid.description}\n\n"
                f"**Difficulty:** {raid.difficulty.value.title()}\n"
                f"**Minimum Level:** {raid.min_level}\n"
                f"**Waves:** {raid.max_waves}\n\n"
                "Use `/raid_join` to participate!"
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="⏰ Starting In",
            value="2 minutes",
            inline=True
        )

        embed.add_field(
            name="👥 Participants",
            value="0 / 10",
            inline=True
        )

        return embed

    async def _update_raid_message(self, raid_id: int):
        """Update raid announcement with participants"""
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()

            if not raid.message_id or not raid.channel_id:
                return

            participants = session.query(RaidParticipant).filter_by(raid_id=raid_id).all()

            channel = self.bot.get_channel(raid.channel_id)
            if not channel:
                return

            try:
                message = await channel.fetch_message(raid.message_id)

                embed = message.embeds[0]

                # Update participants field
                for i, field in enumerate(embed.fields):
                    if "Participants" in field.name:
                        embed.set_field_at(
                            i,
                            name="👥 Participants",
                            value=f"{len(participants)} / {raid.max_players}",
                            inline=True
                        )
                        break

                await message.edit(embed=embed)
            except:
                pass

    async def _start_raid_combat(self, guild_id: int, raid_id: int):
        """Start the raid combat"""
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()
            participants = session.query(RaidParticipant).filter_by(raid_id=raid_id).all()

            if len(participants) < raid.min_players:
                raid.status = RaidStatus.FAILED
                session.commit()

                # Notify
                if raid.channel_id:
                    channel = self.bot.get_channel(raid.channel_id)
                    if channel:
                        await channel.send(
                            f"❌ Raid failed! Not enough participants ({len(participants)}/{raid.min_players})"
                        )

                if guild_id in self.active_raids:
                    del self.active_raids[guild_id]
                return

            raid.status = RaidStatus.IN_PROGRESS
            session.commit()

        # Start wave combat
        for wave_num in range(1, raid.max_waves + 1):
            result = await self._process_wave(raid_id, wave_num)

            if not result:  # Raid failed
                break

            # Brief pause between waves
            await asyncio.sleep(5)

        # Check if raid completed
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()

            if raid.status == RaidStatus.IN_PROGRESS:
                raid.status = RaidStatus.COMPLETED
                raid.completed_at = datetime.utcnow()
                session.commit()

                # Generate loot
                await self._generate_raid_loot(raid_id)

        # Cleanup
        if guild_id in self.active_raids:
            del self.active_raids[guild_id]

    async def _process_wave(self, raid_id: int, wave_number: int) -> bool:
        """Process a raid wave"""
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()
            wave = session.query(RaidWave).filter_by(
                raid_id=raid_id,
                wave_number=wave_number
            ).first()

            raid.current_wave = wave_number
            session.commit()

            # Announce wave
            if raid.channel_id:
                channel = self.bot.get_channel(raid.channel_id)
                if channel:
                    wave_type = "🐲 BOSS WAVE!" if wave.is_boss else f"🌊 Wave {wave_number}"
                    await channel.send(
                        f"## {wave_type}\n"
                        f"**Enemy Health:** {wave.total_enemy_health:,} HP\n"
                        "⚔️ **ATTACK!**"
                    )

            # Combat rounds
            round_num = 0
            while wave.remaining_health > 0:
                round_num += 1

                participants = session.query(RaidParticipant).filter_by(
                    raid_id=raid_id,
                    is_alive=True
                ).all()

                if not participants:
                    raid.status = RaidStatus.FAILED
                    session.commit()

                    if raid.channel_id:
                        channel = self.bot.get_channel(raid.channel_id)
                        if channel:
                            await channel.send("💀 **All participants have fallen! Raid failed!**")

                    return False

                # Each player attacks
                total_damage = 0
                for participant in participants:
                    profile = participant.profile

                    # Calculate attack (with equipment)
                    from cogs.rpg_game import RPGGameCog
                    rpg_cog = self.bot.get_cog('RPGGameCog')
                    if rpg_cog:
                        attack, defense, _, _ = await rpg_cog._calculate_stats(profile.id)
                    else:
                        attack = profile.attack

                    damage = max(10, attack + random.randint(-5, 15))
                    total_damage += damage
                    participant.damage_dealt += damage

                wave.remaining_health = max(0, wave.remaining_health - total_damage)
                session.commit()

                # Show progress every 3 rounds
                if round_num % 3 == 0 and wave.remaining_health > 0:
                    health_pct = (wave.remaining_health / wave.total_enemy_health) * 100
                    if raid.channel_id:
                        channel = self.bot.get_channel(raid.channel_id)
                        if channel:
                            await channel.send(
                                f"⚔️ Round {round_num}: {total_damage:,} damage dealt!\n"
                                f"{self._create_health_bar(health_pct)} {wave.remaining_health:,} HP remaining"
                            )

                await asyncio.sleep(2)

            # Wave complete
            wave.completed = True
            session.commit()

            if raid.channel_id:
                channel = self.bot.get_channel(raid.channel_id)
                if channel:
                    await channel.send(f"✅ **Wave {wave_number} Complete!**")

            return True

    async def _generate_raid_loot(self, raid_id: int):
        """Generate loot and start rolling"""
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()
            participants = session.query(RaidParticipant).filter_by(raid_id=raid_id).all()

            # Generate loot based on difficulty
            loot_count = {
                RaidDifficulty.EASY: 2,
                RaidDifficulty.NORMAL: 3,
                RaidDifficulty.HARD: 4,
                RaidDifficulty.NIGHTMARE: 6
            }

            num_items = loot_count[raid.difficulty]

            # Get items
            items = session.query(RPGItem).filter(
                RPGItem.level_required <= raid.min_level + 10
            ).order_by(RPGItem.rarity.desc()).limit(num_items * 2).all()

            dropped_items = random.sample(items, min(num_items, len(items)))

            for item in dropped_items:
                loot = RaidLoot(
                    raid_id=raid_id,
                    item_id=item.id,
                    roll_closes_at=datetime.utcnow() + timedelta(seconds=60)
                )
                session.add(loot)

            session.commit()

        # Announce loot
        if raid.channel_id:
            channel = self.bot.get_channel(raid.channel_id)
            if channel:
                embed = discord.Embed(
                    title="🎁 Raid Complete - Loot Drops!",
                    description="Roll for items! You have 60 seconds.",
                    color=discord.Color.gold()
                )

                for loot in dropped_items:
                    rarity_emoji = self._get_rarity_emoji(loot.rarity)
                    embed.add_field(
                        name=f"{loot.emoji or '•'} {loot.name} {rarity_emoji}",
                        value=f"ID: {loot.id} | Use buttons below",
                        inline=False
                    )

                view = LootRollView(self.bot, raid_id)
                await channel.send(embed=embed, view=view)

                # Show contribution
                await self._show_raid_results(raid_id)

    async def _show_raid_results(self, raid_id: int):
        """Show final raid results"""
        with db.session_scope() as session:
            raid = session.query(Raid).filter_by(id=raid_id).first()
            participants = session.query(RaidParticipant).filter_by(
                raid_id=raid_id
            ).order_by(RaidParticipant.damage_dealt.desc()).all()

            embed = discord.Embed(
                title="📊 Raid Results",
                color=discord.Color.blue()
            )

            # Top contributors
            top_text = []
            total_damage = sum(p.damage_dealt for p in participants)

            for i, p in enumerate(participants[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                contribution_pct = (p.damage_dealt / total_damage) * 100 if total_damage > 0 else 0
                top_text.append(
                    f"{medal} <@{p.profile.member.user_id}> - {p.damage_dealt:,} dmg ({contribution_pct:.1f}%)"
                )

            embed.add_field(
                name="⚔️ Top Contributors",
                value="\n".join(top_text),
                inline=False
            )

            # EXP rewards based on contribution
            for participant in participants:
                contribution_pct = (participant.damage_dealt / total_damage) * 100 if total_damage > 0 else 0
                base_exp = raid.min_level * 50
                exp_reward = int(base_exp * (contribution_pct / 100))

                profile = participant.profile
                profile.experience += exp_reward

            session.commit()

            if raid.channel_id:
                channel = self.bot.get_channel(raid.channel_id)
                if channel:
                    await channel.send(embed=embed)

    @tasks.loop(seconds=30)
    async def check_raids(self):
        """Check for expired raids"""
        with db.session_scope() as session:
            expired = session.query(Raid).filter(
                Raid.status == RaidStatus.IN_PROGRESS,
                Raid.ends_at < datetime.utcnow()
            ).all()

            for raid in expired:
                raid.status = RaidStatus.FAILED
                session.commit()

                # Remove from active
                for guild_id, raid_id in list(self.active_raids.items()):
                    if raid_id == raid.id:
                        del self.active_raids[guild_id]

    @tasks.loop(seconds=10)
    async def process_loot_rolls(self):
        """Process completed loot rolls"""
        with db.session_scope() as session:
            completed = session.query(RaidLoot).filter(
                RaidLoot.winner_profile_id == None,
                RaidLoot.roll_closes_at < datetime.utcnow()
            ).all()

            for loot in completed:
                rolls = session.query(LootRoll).filter_by(loot_id=loot.id).all()

                if not rolls:
                    continue

                # Need rolls first
                need_rolls = [r for r in rolls if r.roll_type == RollType.NEED]
                greed_rolls = [r for r in rolls if r.roll_type == RollType.GREED]

                winner = None
                if need_rolls:
                    winner = max(need_rolls, key=lambda r: r.roll_value)
                elif greed_rolls:
                    winner = max(greed_rolls, key=lambda r: r.roll_value)

                if winner:
                    loot.winner_profile_id = winner.profile_id

                    # Add to inventory
                    from models_rpg import InventoryItem
                    inv_item = session.query(InventoryItem).filter_by(
                        profile_id=winner.profile_id,
                        item_id=loot.item_id
                    ).first()

                    if inv_item:
                        inv_item.quantity += 1
                    else:
                        inv_item = InventoryItem(
                            profile_id=winner.profile_id,
                            item_id=loot.item_id,
                            quantity=1
                        )
                        session.add(inv_item)

                    session.commit()

                    # Announce
                    raid = loot.raid
                    if raid.channel_id:
                        channel = self.bot.get_channel(raid.channel_id)
                        if channel:
                            item = loot.item
                            await channel.send(
                                f"🎉 <@{winner.profile.member.user_id}> won **{item.name}** "
                                f"with a roll of **{winner.roll_value}**!"
                            )

    def _create_health_bar(self, percentage: float, length: int = 20) -> str:
        """Create health bar"""
        filled = int(length * percentage / 100)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}] {percentage:.1f}%"

    def _get_rarity_emoji(self, rarity) -> str:
        """Get rarity emoji"""
        from models_rpg import RPGItemRarity
        emojis = {
            RPGItemRarity.COMMON: "⚪",
            RPGItemRarity.UNCOMMON: "🟢",
            RPGItemRarity.RARE: "🔵",
            RPGItemRarity.EPIC: "🟣",
            RPGItemRarity.LEGENDARY: "🟠",
            RPGItemRarity.MYTHIC: "🔴"
        }
        return emojis.get(rarity, "⚪")


class LootRollView(discord.ui.View):
    """Loot rolling UI"""

    def __init__(self, bot, raid_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.raid_id = raid_id

    @discord.ui.button(label="⚔️ Need", style=discord.ButtonStyle.green, custom_id="need")
    async def need_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Roll need"""
        await self._process_roll(interaction, RollType.NEED)

    @discord.ui.button(label="💰 Greed", style=discord.ButtonStyle.blurple, custom_id="greed")
    async def greed_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Roll greed"""
        await self._process_roll(interaction, RollType.GREED)

    @discord.ui.button(label="❌ Pass", style=discord.ButtonStyle.grey, custom_id="pass")
    async def pass_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pass on loot"""
        await self._process_roll(interaction, RollType.PASS)

    async def _process_roll(self, interaction: discord.Interaction, roll_type: RollType):
        """Process a loot roll"""
        with db.session_scope() as session:
            # Get participant
            from utils.helpers import get_or_create_member
            member = await get_or_create_member(
                interaction.guild.id,
                interaction.user.id,
                interaction.user.name
            )

            from models_rpg import UserProfile
            profile = session.query(UserProfile).filter_by(member_id=member.id).first()

            if not profile:
                await interaction.response.send_message(
                    "❌ You didn't participate in this raid!",
                    ephemeral=True
                )
                return

            # Check if participant
            from models_rpg import RaidParticipant
            participant = session.query(RaidParticipant).filter_by(
                raid_id=self.raid_id,
                profile_id=profile.id
            ).first()

            if not participant:
                await interaction.response.send_message(
                    "❌ You didn't participate in this raid!",
                    ephemeral=True
                )
                return

            # Get all active loot
            loot_items = session.query(RaidLoot).filter_by(
                raid_id=self.raid_id,
                winner_profile_id=None
            ).all()

            for loot in loot_items:
                # Check if already rolled
                existing = session.query(LootRoll).filter_by(
                    loot_id=loot.id,
                    profile_id=profile.id
                ).first()

                if not existing:
                    roll_value = random.randint(1, 100) if roll_type != RollType.PASS else None

                    roll = LootRoll(
                        loot_id=loot.id,
                        profile_id=profile.id,
                        roll_type=roll_type,
                        roll_value=roll_value
                    )
                    session.add(roll)

            session.commit()

        if roll_type == RollType.PASS:
            await interaction.response.send_message(
                "✅ You passed on all loot.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🎲 You rolled {roll_type.value.upper()} on all items!",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(RaidsCog(bot))