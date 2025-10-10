# File: cogs/dungeon.py
# Location: /bot/cogs/dungeon.py

import discord
from discord.ext import commands
from discord import app_commands
import random
import json
import logging
from typing import List, Tuple, Optional

from models_extended import UserProfile, RPGItem, Enemy, InventoryItem
from models_enhanced import DungeonRun, DungeonLoot, DungeonStatus, DungeonDifficulty
from database import db
from utils.helpers import create_embed

logger = logging.getLogger(__name__)


class DungeonCog(commands.Cog):
    """Roguelike dungeon crawler with visual exploration"""

    def __init__(self, bot):
        self.bot = bot

        # Tile types
        self.tiles = {
            'wall': '⬛',
            'floor': '⬜',
            'player': '🧙',
            'enemy': '👹',
            'treasure': '💎',
            'exit': '🚪',
            'boss': '🐲',
            'shop': '🏪',
            'rest': '🛏️',
            'trap': '⚠️',
            'unknown': '🌫️'
        }

    @app_commands.command(name="dungeon_enter", description="Enter a dungeon")
    @app_commands.guild_only()
    @app_commands.describe(difficulty="Dungeon difficulty")
    async def dungeon_enter(self, interaction: discord.Interaction, difficulty: str = "normal"):
        """Start dungeon exploration"""
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

            # Check for active dungeon
            active = session.query(DungeonRun).filter_by(
                profile_id=profile.id,
                status=DungeonStatus.ACTIVE
            ).first()

            if active:
                await interaction.response.send_message(
                    "❌ You're already in a dungeon! Use `/dungeon_map` to continue.",
                    ephemeral=True
                )
                return

            try:
                diff_enum = DungeonDifficulty(difficulty.lower())
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid difficulty. Use: easy, normal, hard, or insane",
                    ephemeral=True
                )
                return

            # Create dungeon run
            dungeon = DungeonRun(
                profile_id=profile.id,
                name=f"The Dark {diff_enum.value.title()} Depths",
                difficulty=diff_enum,
                seed=str(random.randint(1000, 9999))
            )

            # Generate first floor
            dungeon_map = self._generate_floor(10, 10, diff_enum)

            # Set starting position
            start_pos = self._find_start_position(dungeon_map)

            # Initialize state
            state = {
                'position': start_pos,
                'health': profile.max_health,
                'map': dungeon_map,
                'visible': self._calculate_vision(dungeon_map, start_pos, vision_range=2),
                'keys': 0,
                'potions': 3
            }

            dungeon.state = state
            session.add(dungeon)
            session.commit()

        embed = await self._create_dungeon_embed(dungeon)
        view = DungeonNavigationView(self, dungeon.id)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name="dungeon_map", description="View your current dungeon")
    @app_commands.guild_only()
    async def dungeon_map(self, interaction: discord.Interaction):
        """View dungeon map"""
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

            dungeon = session.query(DungeonRun).filter_by(
                profile_id=profile.id,
                status=DungeonStatus.ACTIVE
            ).first()

            if not dungeon:
                await interaction.response.send_message(
                    "❌ You're not in a dungeon! Use `/dungeon_enter` to start.",
                    ephemeral=True
                )
                return

            embed = await self._create_dungeon_embed(dungeon)
            view = DungeonNavigationView(self, dungeon.id)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    async def move_player(self, dungeon_id: int, direction: str) -> Tuple[bool, str, Optional[dict]]:
        """Move player in direction"""
        directions = {
            'north': (0, -1),
            'south': (0, 1),
            'east': (1, 0),
            'west': (-1, 0)
        }

        if direction not in directions:
            return False, "Invalid direction!", None

        with db.session_scope() as session:
            dungeon = session.query(DungeonRun).filter_by(id=dungeon_id).first()

            if not dungeon or dungeon.status != DungeonStatus.ACTIVE:
                return False, "Dungeon not active!", None

            state = dungeon.state
            current_pos = state['position']
            dx, dy = directions[direction]
            new_pos = [current_pos[0] + dx, current_pos[1] + dy]

            # Check bounds
            if not self._is_valid_position(state['map'], new_pos):
                return False, "Can't go that way!", None

            # Check tile
            tile_type = state['map'][new_pos[1]][new_pos[0]]

            if tile_type == 'wall':
                return False, "There's a wall there!", None

            # Move player
            state['position'] = new_pos
            state['visible'] = self._calculate_vision(state['map'], new_pos, vision_range=2)

            dungeon.rooms_explored += 1

            # Handle tile effects
            encounter = None
            message = "Moved."

            if tile_type == 'enemy':
                encounter = await self._create_combat_encounter(dungeon, session)
                message = "You encountered an enemy!"
                # Mark tile as explored
                state['map'][new_pos[1]][new_pos[0]] = 'floor'

            elif tile_type == 'treasure':
                loot = await self._generate_loot(dungeon, session)
                state['map'][new_pos[1]][new_pos[0]] = 'floor'
                dungeon.treasure_found += 1
                message = f"Found treasure: {loot['name']}!"

            elif tile_type == 'exit':
                # Next floor
                dungeon.current_floor += 1
                if dungeon.current_floor > dungeon.max_floor:
                    dungeon.status = DungeonStatus.COMPLETED
                    dungeon.completed_at = datetime.utcnow()
                    message = "🎉 You've completed the dungeon!"
                else:
                    # Generate new floor
                    new_map = self._generate_floor(
                        12 + dungeon.current_floor,
                        12 + dungeon.current_floor,
                        dungeon.difficulty
                    )
                    start = self._find_start_position(new_map)
                    state['map'] = new_map
                    state['position'] = start
                    state['visible'] = self._calculate_vision(new_map, start, 2)
                    message = f"Descended to Floor {dungeon.current_floor}!"

            elif tile_type == 'rest':
                # Heal
                profile = dungeon.profile
                heal_amount = int(profile.max_health * 0.5)
                state['health'] = min(state['health'] + heal_amount, profile.max_health)
                state['map'][new_pos[1]][new_pos[0]] = 'floor'
                message = f"Rested and healed {heal_amount} HP!"

            elif tile_type == 'boss':
                encounter = await self._create_boss_encounter(dungeon, session)
                message = "⚠️ BOSS BATTLE!"

            dungeon.state = state
            session.commit()

            return True, message, encounter

    def _generate_floor(self, width: int, height: int, difficulty: DungeonDifficulty) -> List[List[str]]:
        """Generate a dungeon floor"""
        # Create empty map
        dungeon_map = [['wall' for _ in range(width)] for _ in range(height)]

        # Carve rooms
        rooms = []
        num_rooms = random.randint(5, 10)

        for _ in range(num_rooms):
            room_w = random.randint(3, 7)
            room_h = random.randint(3, 7)
            room_x = random.randint(1, width - room_w - 1)
            room_y = random.randint(1, height - room_h - 1)

            # Check overlap
            overlap = False
            for r in rooms:
                if (room_x < r[0] + r[2] + 1 and room_x + room_w + 1 > r[0] and
                        room_y < r[1] + r[3] + 1 and room_y + room_h + 1 > r[1]):
                    overlap = True
                    break

            if not overlap:
                # Carve room
                for y in range(room_y, room_y + room_h):
                    for x in range(room_x, room_x + room_w):
                        dungeon_map[y][x] = 'floor'

                rooms.append([room_x, room_y, room_w, room_h])

        # Connect rooms with corridors
        for i in range(len(rooms) - 1):
            x1, y1 = rooms[i][0] + rooms[i][2] // 2, rooms[i][1] + rooms[i][3] // 2
            x2, y2 = rooms[i + 1][0] + rooms[i + 1][2] // 2, rooms[i + 1][1] + rooms[i + 1][3] // 2

            # Horizontal corridor
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < width and 0 <= y1 < height:
                    dungeon_map[y1][x] = 'floor'

            # Vertical corridor
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x2 < width and 0 <= y < height:
                    dungeon_map[y][x2] = 'floor'

        # Place special tiles
        floor_tiles = []
        for y in range(height):
            for x in range(width):
                if dungeon_map[y][x] == 'floor':
                    floor_tiles.append((x, y))

        if floor_tiles:
            # Exit in last room
            exit_pos = random.choice([(x, y) for x in range(rooms[-1][0], rooms[-1][0] + rooms[-1][2])
                                      for y in range(rooms[-1][1], rooms[-1][1] + rooms[-1][3])])
            dungeon_map[exit_pos[1]][exit_pos[0]] = 'exit'

            # Enemies
            num_enemies = int(len(floor_tiles) * 0.15)
            for pos in random.sample(floor_tiles, min(num_enemies, len(floor_tiles))):
                if dungeon_map[pos[1]][pos[0]] == 'floor':
                    dungeon_map[pos[1]][pos[0]] = 'enemy'

            # Treasure
            num_treasure = random.randint(2, 5)
            for pos in random.sample(floor_tiles, min(num_treasure, len(floor_tiles))):
                if dungeon_map[pos[1]][pos[0]] == 'floor':
                    dungeon_map[pos[1]][pos[0]] = 'treasure'

            # Rest area
            for pos in random.sample(floor_tiles, min(1, len(floor_tiles))):
                if dungeon_map[pos[1]][pos[0]] == 'floor':
                    dungeon_map[pos[1]][pos[0]] = 'rest'

        return dungeon_map

    def _find_start_position(self, dungeon_map: List[List[str]]) -> List[int]:
        """Find starting position (first floor tile)"""
        for y in range(len(dungeon_map)):
            for x in range(len(dungeon_map[0])):
                if dungeon_map[y][x] == 'floor':
                    return [x, y]
        return [1, 1]

    def _calculate_vision(self, dungeon_map: List[List[str]], pos: List[int], vision_range: int) -> List[List[int]]:
        """Calculate visible tiles"""
        visible = []
        x, y = pos

        for dy in range(-vision_range, vision_range + 1):
            for dx in range(-vision_range, vision_range + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < len(dungeon_map[0]) and 0 <= ny < len(dungeon_map):
                    if abs(dx) + abs(dy) <= vision_range:  # Manhattan distance
                        visible.append([nx, ny])

        return visible

    def _is_valid_position(self, dungeon_map: List[List[str]], pos: List[int]) -> bool:
        """Check if position is valid"""
        x, y = pos
        return 0 <= x < len(dungeon_map[0]) and 0 <= y < len(dungeon_map)

    async def _create_dungeon_embed(self, dungeon: DungeonRun) -> discord.Embed:
        """Create dungeon visualization embed"""
        state = dungeon.state
        dungeon_map = state['map']
        player_pos = state['position']
        visible = state['visible']

        # Create visual representation
        map_display = []
        for y in range(len(dungeon_map)):
            row = []
            for x in range(len(dungeon_map[0])):
                if [x, y] == player_pos:
                    row.append(self.tiles['player'])
                elif [x, y] in visible:
                    tile_type = dungeon_map[y][x]
                    row.append(self.tiles.get(tile_type, self.tiles['floor']))
                else:
                    row.append(self.tiles['unknown'])
            map_display.append(''.join(row))

        # Crop to show around player (11x11 view)
        view_size = 11
        half_view = view_size // 2
        px, py = player_pos

        start_y = max(0, py - half_view)
        end_y = min(len(dungeon_map), py + half_view + 1)
        start_x = max(0, px - half_view)
        end_x = min(len(dungeon_map[0]), px + half_view + 1)

        cropped_view = []
        for y in range(start_y, end_y):
            row = map_display[y][start_x:end_x]
            cropped_view.append(row)

        embed = discord.Embed(
            title=f"🗺️ {dungeon.name} - Floor {dungeon.current_floor}",
            description=f"```\n" + "\n".join(cropped_view) + "\n```",
            color=discord.Color.dark_purple()
        )

        embed.add_field(
            name="❤️ Health",
            value=f"{state['health']}/{dungeon.profile.max_health}",
            inline=True
        )

        embed.add_field(
            name="🗝️ Keys",
            value=state.get('keys', 0),
            inline=True
        )

        embed.add_field(
            name="🧪 Potions",
            value=state.get('potions', 0),
            inline=True
        )

        embed.add_field(
            name="📊 Progress",
            value=f"**Monsters Killed:** {dungeon.monsters_killed}\n**Treasure Found:** {dungeon.treasure_found}",
            inline=False
        )

        embed.set_footer(text="Use the buttons below to move")

        return embed

    async def _create_combat_encounter(self, dungeon: DungeonRun, session) -> dict:
        """Create combat encounter"""
        from models_extended import Enemy

        enemies = session.query(Enemy).filter(
            Enemy.level >= dungeon.current_floor,
            Enemy.level <= dungeon.current_floor + 3
        ).all()

        if not enemies:
            return None

        enemy = random.choice(enemies)

        return {
            'type': 'combat',
            'enemy_id': enemy.id,
            'enemy_name': enemy.name,
            'enemy_health': enemy.health,
            'enemy_attack': enemy.attack
        }

    async def _create_boss_encounter(self, dungeon: DungeonRun, session) -> dict:
        """Create boss encounter"""
        from models_extended import Enemy

        # Get strongest enemy for this level
        boss = session.query(Enemy).filter(
            Enemy.level >= dungeon.current_floor + 2
        ).order_by(Enemy.level.desc()).first()

        if not boss:
            return await self._create_combat_encounter(dungeon, session)

        return {
            'type': 'boss',
            'enemy_id': boss.id,
            'enemy_name': boss.name,
            'enemy_health': boss.health * 3,
            'enemy_attack': boss.attack * 2
        }

    async def _generate_loot(self, dungeon: DungeonRun, session) -> dict:
        """Generate loot drop"""
        from models_extended import RPGItem, InventoryItem

        items = session.query(RPGItem).filter(
            RPGItem.level_required <= dungeon.current_floor + 5
        ).all()

        if not items:
            return {'name': 'Gold', 'amount': random.randint(50, 200)}

        item = random.choice(items)

        # Add to inventory
        inv_item = session.query(InventoryItem).filter_by(
            profile_id=dungeon.profile_id,
            item_id=item.id
        ).first()

        if inv_item:
            inv_item.quantity += 1
        else:
            inv_item = InventoryItem(
                profile_id=dungeon.profile_id,
                item_id=item.id,
                quantity=1
            )
            session.add(inv_item)

        # Log
        loot = DungeonLoot(
            run_id=dungeon.id,
            item_id=item.id,
            floor_found=dungeon.current_floor
        )
        session.add(loot)

        return {'name': item.name, 'emoji': item.emoji}


class DungeonNavigationView(discord.ui.View):
    """Dungeon navigation buttons"""

    def __init__(self, cog, dungeon_id: int):
        super().__init__(timeout=600)
        self.cog = cog
        self.dungeon_id = dungeon_id

    @discord.ui.button(label="⬆️", style=discord.ButtonStyle.secondary, row=0)
    async def move_north(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, 'north')

    @discord.ui.button(label="⬇️", style=discord.ButtonStyle.secondary, row=1)
    async def move_south(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, 'south')

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def move_west(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, 'west')

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def move_east(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_move(interaction, 'east')

    @discord.ui.button(label="🧪 Potion", style=discord.ButtonStyle.green, row=2)
    async def use_potion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Use healing potion"""
        with db.session_scope() as session:
            dungeon = session.query(DungeonRun).filter_by(id=self.dungeon_id).first()
            state = dungeon.state

            if state.get('potions', 0) <= 0:
                await interaction.response.send_message("❌ No potions left!", ephemeral=True)
                return

            profile = dungeon.profile
            heal_amount = int(profile.max_health * 0.5)
            state['health'] = min(state['health'] + heal_amount, profile.max_health)
            state['potions'] -= 1

            dungeon.state = state
            session.commit()

            embed = await self.cog._create_dungeon_embed(dungeon)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🚪 Exit Dungeon", style=discord.ButtonStyle.danger, row=2)
    async def exit_dungeon(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Exit dungeon"""
        with db.session_scope() as session:
            dungeon = session.query(DungeonRun).filter_by(id=self.dungeon_id).first()
            dungeon.status = DungeonStatus.ABANDONED
            session.commit()

        await interaction.response.edit_message(
            content="🚪 You've exited the dungeon.",
            embed=None,
            view=None
        )

    async def _handle_move(self, interaction: discord.Interaction, direction: str):
        """Handle movement"""
        success, message, encounter = await self.cog.move_player(self.dungeon_id, direction)

        if not success:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return

        with db.session_scope() as session:
            dungeon = session.query(DungeonRun).filter_by(id=self.dungeon_id).first()
            embed = await self.cog._create_dungeon_embed(dungeon)

            if encounter:
                # Combat encounter
                await interaction.response.edit_message(embed=embed, view=self)
                await interaction.followup.send(
                    f"⚔️ {message}\n**{encounter['enemy_name']}** HP: {encounter['enemy_health']}",
                    ephemeral=False
                )
            else:
                await interaction.response.edit_message(
                    content=message if message != "Moved." else None,
                    embed=embed,
                    view=self
                )


async def setup(bot):
    await bot.add_cog(DungeonCog(bot))