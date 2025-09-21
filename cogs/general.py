"""
General utility commands for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands
import random
import re
from typing import List, Tuple


class GeneralCog(commands.Cog):
    """General utility commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="roll", description="Roll dice using standard notation (e.g., 1d20, 2d6+3)")
    @app_commands.describe(
        dice="Dice notation (e.g., 1d20, 2d6+3, 4d6kh3). Supports modifiers and keep highest/lowest."
    )
    async def roll_dice(self, interaction: discord.Interaction, dice: str):
        """Roll dice with support for various notations."""
        try:
            result = self.parse_and_roll_dice(dice)
            
            embed = discord.Embed(
                title="🎲 Dice Roll",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Request",
                value=f"`{dice}`",
                inline=True
            )
            
            embed.add_field(
                name="Result",
                value=f"**{result['total']}**",
                inline=True
            )
            
            if result['breakdown']:
                embed.add_field(
                    name="Breakdown",
                    value=result['breakdown'],
                    inline=False
                )
            
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Dice Notation",
                description=str(e),
                color=discord.Color.red()
            )
            embed.add_field(
                name="Examples",
                value=(
                    "• `1d20` - Roll a 20-sided die\n"
                    "• `2d6+3` - Roll two 6-sided dice and add 3\n"
                    "• `4d6kh3` - Roll four 6-sided dice, keep highest 3\n"
                    "• `6d6kl4` - Roll six 6-sided dice, keep lowest 4\n"
                    "• `1d20+5-2` - Roll a d20, add 5, subtract 2\n"
                    "• `2d10*2` - Roll two d10s and multiply by 2"
                ),
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while rolling dice.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def parse_and_roll_dice(self, dice_str: str) -> dict:
        """Parse dice notation and roll the dice."""
        dice_str = dice_str.lower().replace(" ", "")
        
        # Validate basic format
        if not re.match(r'^[0-9d+\-*/khl]+$', dice_str):
            raise ValueError("Invalid characters in dice notation. Use only numbers, d, +, -, *, /, k, h, l")
        
        # Split by dice groups (split on + or - but keep the operators)
        parts = re.split(r'([+\-*/])', dice_str)
        
        total = 0
        breakdown_parts = []
        first_part = True
        current_operator = '+'
        
        for part in parts:
            if part in ['+', '-', '*', '/']:
                current_operator = part
                continue
            
            if not part:
                continue
            
            # Check if this part contains dice notation
            if 'd' in part:
                dice_result = self.roll_dice_group(part)
                value = dice_result['total']
                breakdown_parts.append(f"{part} → {dice_result['breakdown']}")
            else:
                # It's just a number
                try:
                    value = int(part)
                    breakdown_parts.append(str(value))
                except ValueError:
                    raise ValueError(f"Invalid number: {part}")
            
            # Apply the operation
            if first_part:
                total = value
                first_part = False
            else:
                if current_operator == '+':
                    total += value
                elif current_operator == '-':
                    total -= value
                elif current_operator == '*':
                    total *= value
                elif current_operator == '/':
                    if value == 0:
                        raise ValueError("Cannot divide by zero")
                    total = int(total / value)  # Integer division for dice
        
        return {
            'total': total,
            'breakdown': ' '.join(breakdown_parts) if len(breakdown_parts) > 1 else breakdown_parts[0] if breakdown_parts else str(total)
        }
    
    def roll_dice_group(self, dice_group: str) -> dict:
        """Roll a single group of dice (e.g., '3d6kh2')."""
        # Parse keep highest/lowest
        keep_highest = None
        keep_lowest = None
        
        if 'kh' in dice_group:
            dice_part, keep_part = dice_group.split('kh')
            keep_highest = int(keep_part)
        elif 'kl' in dice_group:
            dice_part, keep_part = dice_group.split('kl')
            keep_lowest = int(keep_part)
        else:
            dice_part = dice_group
        
        # Parse number of dice and die size
        if 'd' not in dice_part:
            raise ValueError(f"Invalid dice notation: {dice_group}")
        
        parts = dice_part.split('d')
        if len(parts) != 2:
            raise ValueError(f"Invalid dice notation: {dice_group}")
        
        try:
            num_dice = int(parts[0]) if parts[0] else 1
            die_size = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid dice notation: {dice_group}")
        
        # Validate ranges
        if num_dice < 1 or num_dice > 100:
            raise ValueError("Number of dice must be between 1 and 100")
        
        if die_size < 2 or die_size > 1000:
            raise ValueError("Die size must be between 2 and 1000")
        
        if keep_highest and (keep_highest < 1 or keep_highest > num_dice):
            raise ValueError("Keep highest must be between 1 and number of dice")
        
        if keep_lowest and (keep_lowest < 1 or keep_lowest > num_dice):
            raise ValueError("Keep lowest must be between 1 and number of dice")
        
        # Roll the dice
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        
        # Apply keep highest/lowest
        kept_rolls = rolls.copy()
        dropped_rolls = []
        
        if keep_highest:
            sorted_rolls = sorted(rolls, reverse=True)
            kept_rolls = sorted_rolls[:keep_highest]
            dropped_rolls = sorted_rolls[keep_highest:]
        elif keep_lowest:
            sorted_rolls = sorted(rolls)
            kept_rolls = sorted_rolls[:keep_lowest]
            dropped_rolls = sorted_rolls[keep_lowest:]
        
        total = sum(kept_rolls)
        
        # Create breakdown string
        if keep_highest or keep_lowest:
            kept_str = ', '.join(str(r) for r in kept_rolls)
            if dropped_rolls:
                dropped_str = ', '.join(f"~~{r}~~" for r in dropped_rolls)
                breakdown = f"[{kept_str}, {dropped_str}] = {total}"
            else:
                breakdown = f"[{kept_str}] = {total}"
        else:
            if len(rolls) == 1:
                breakdown = str(total)
            else:
                rolls_str = ', '.join(str(r) for r in rolls)
                breakdown = f"[{rolls_str}] = {total}"
        
        return {
            'total': total,
            'breakdown': breakdown,
            'rolls': rolls,
            'kept_rolls': kept_rolls,
            'dropped_rolls': dropped_rolls
        }
    
    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        """Flip a coin."""
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙"
        
        embed = discord.Embed(
            title=f"{emoji} Coin Flip",
            description=f"**{result}**",
            color=discord.Color.gold()
        )
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="choose", description="Choose randomly from a list of options")
    @app_commands.describe(
        options="Comma-separated list of options to choose from"
    )
    async def choose(self, interaction: discord.Interaction, options: str):
        """Choose randomly from a list of options."""
        option_list = [opt.strip() for opt in options.split(',') if opt.strip()]
        
        if len(option_list) < 2:
            embed = discord.Embed(
                title="❌ Invalid Options",
                description="Please provide at least 2 options separated by commas.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Example",
                value="`/choose options:pizza, tacos, sushi, burgers`",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if len(option_list) > 20:
            embed = discord.Embed(
                title="❌ Too Many Options",
                description="Please provide no more than 20 options.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        choice = random.choice(option_list)
        
        embed = discord.Embed(
            title="🎯 Random Choice",
            description=f"**{choice}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Options",
            value=", ".join(f"`{opt}`" for opt in option_list),
            inline=False
        )
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="random", description="Generate a random number")
    @app_commands.describe(
        minimum="Minimum value (default: 1)",
        maximum="Maximum value (default: 100)"
    )
    async def random_number(self, interaction: discord.Interaction, minimum: int = 1, maximum: int = 100):
        """Generate a random number between min and max."""
        if minimum >= maximum:
            embed = discord.Embed(
                title="❌ Invalid Range",
                description="Minimum value must be less than maximum value.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if maximum - minimum > 1000000:
            embed = discord.Embed(
                title="❌ Range Too Large",
                description="Range must be 1,000,000 or less.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        result = random.randint(minimum, maximum)
        
        embed = discord.Embed(
            title="🔢 Random Number",
            description=f"**{result}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Range",
            value=f"{minimum} - {maximum}",
            inline=True
        )
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your yes/no question")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        """Magic 8-ball responses."""
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.",
            "Very doubtful."
        ]
        
        response = random.choice(responses)
        
        # Determine color based on response type
        positive_responses = responses[:10]
        neutral_responses = responses[10:15]
        negative_responses = responses[15:]
        
        if response in positive_responses:
            color = discord.Color.green()
        elif response in neutral_responses:
            color = discord.Color.yellow()
        else:
            color = discord.Color.red()
        
        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            color=color
        )
        
        embed.add_field(
            name="Question",
            value=question,
            inline=False
        )
        
        embed.add_field(
            name="Answer",
            value=f"*{response}*",
            inline=False
        )
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(GeneralCog(bot))