"""
Poll commands for the Guild Management Bot - FIXED VERSION
"""
import discord
from discord.ext import commands
from sqlalchemy import select, and_, update
from datetime import datetime, timezone

from database import Poll, PollVote, get_session
from views.polls import PollBuilderModal, PollCreatorView
from utils.permissions import PermissionChecker


class Polls(commands.Cog):
    """Poll creation and management commands."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="poll", description="Create a new poll")
    async def create_poll(self, interaction: discord.Interaction):
        """Create a new poll through the UI."""
        # Check permissions
        try:
            from utils.cache import get_config
            config = await get_config(self.bot, interaction.guild_id, "poll_permissions", {})
            allowed_roles = config.get("creator_roles", [])

            if allowed_roles:
                user_roles = [role.id for role in interaction.user.roles]
                if not any(role_id in user_roles for role_id in allowed_roles):
                    embed = discord.Embed(
                        title="❌ Permission Denied",
                        description="You don't have permission to create polls.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
        except (AttributeError, TypeError):
            # If config check fails, allow all users
            pass

        modal = PollBuilderModal()
        await interaction.response.send_modal(modal)

    @discord.app_commands.command(name="poll-status", description="Check the status of a poll")
    @discord.app_commands.describe(poll_id="ID of the poll to check")
    async def poll_status(self, interaction: discord.Interaction, poll_id: int):
        """Check the status of a specific poll."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Poll).where(
                        and_(
                            Poll.id == poll_id,
                            Poll.guild_id == interaction.guild_id
                        )
                    )
                )
                poll = result.scalar_one_or_none()

                if not poll:
                    embed = discord.Embed(
                        title="❌ Poll Not Found",
                        description=f"No poll found with ID {poll_id} in this server.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Get vote counts
                from sqlalchemy import func
                vote_counts = {}
                for i in range(len(poll.options)):
                    count_result = await session.execute(
                        select(func.count(PollVote.id))
                        .where(
                            and_(
                                PollVote.poll_id == poll_id,
                                PollVote.options.contains([i])
                            )
                        )
                    )
                    vote_counts[i] = count_result.scalar() or 0

                total_votes = sum(vote_counts.values())

            # Create status embed
            embed = discord.Embed(
                title="📊 Poll Status",
                description=poll.question,
                color=discord.Color.blue()
            )

            # Basic info
            embed.add_field(
                name="📋 Details",
                value=(
                    f"**ID:** {poll.id}\n"
                    f"**Status:** {poll.status.title()}\n"  # FIXED: Use status field
                    f"**Created:** {discord.utils.format_dt(poll.created_at, 'R')}\n"
                    f"**Anonymous:** {'Yes' if poll.is_anonymous else 'No'}"
                ),
                inline=True
            )

            embed.add_field(
                name="📈 Voting",
                value=(
                    f"**Total Votes:** {total_votes}\n"
                    f"**Options:** {len(poll.options)}"
                ),
                inline=True
            )

            # Show end time if applicable
            if poll.ends_at:
                if poll.status == 'active':  # FIXED: Use status field
                    embed.add_field(
                        name="⏰ Timing",
                        value=f"**Ends:** {discord.utils.format_dt(poll.ends_at, 'R')}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="⏰ Timing",
                        value=f"**Ended:** {discord.utils.format_dt(poll.ends_at, 'R')}",
                        inline=True
                    )

            # Show results if not anonymous or user is admin
            if not poll.is_anonymous or PermissionChecker.is_admin(interaction.user):
                results_text = []
                for i, option in enumerate(poll.options):
                    count = vote_counts.get(i, 0)
                    percentage = (count / total_votes * 100) if total_votes > 0 else 0

                    # Create visual bar
                    bar_length = 10
                    filled = int(percentage / 100 * bar_length)
                    bar = "█" * filled + "░" * (bar_length - filled)

                    results_text.append(
                        f"{chr(127462 + i)} **{option}**\n`{bar}` {count} votes ({percentage:.1f}%)"
                    )

                embed.add_field(
                    name="📊 Current Results",
                    value="\n\n".join(results_text[:5]),  # Show first 5 options
                    inline=False
                )

                if len(poll.options) > 5:
                    embed.set_footer(text=f"Showing first 5 of {len(poll.options)} options")

            # Channel info
            channel = interaction.guild.get_channel(poll.channel_id)
            if channel:
                embed.add_field(
                    name="📍 Location",
                    value=f"**Channel:** {channel.mention}",
                    inline=True
                )

                if poll.message_id:
                    message_link = f"https://discord.com/channels/{interaction.guild_id}/{poll.channel_id}/{poll.message_id}"
                    embed.add_field(
                        name="🔗 Message Link",
                        value=f"[View Poll]({message_link})",
                        inline=True
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (AttributeError, TypeError, ValueError) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to retrieve poll status: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Discord Error",
                description=f"Failed to display poll status: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="close-poll", description="Close an active poll")
    @discord.app_commands.describe(poll_id="ID of the poll to close")
    async def close_poll(self, interaction: discord.Interaction, poll_id: int):
        """Close an active poll."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "close polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            async with get_session() as session:
                # Check if poll exists and is active
                result = await session.execute(
                    select(Poll).where(
                        and_(
                            Poll.id == poll_id,
                            Poll.guild_id == interaction.guild_id
                        )
                    )
                )
                poll = result.scalar_one_or_none()

                if not poll:
                    embed = discord.Embed(
                        title="❌ Poll Not Found",
                        description=f"No poll found with ID {poll_id} in this server.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                if poll.status != 'active':  # FIXED: Use status field
                    embed = discord.Embed(
                        title="❌ Poll Already Closed",
                        description=f"Poll #{poll_id} is already closed.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Close the poll
                await session.execute(
                    update(Poll)
                    .where(Poll.id == poll_id)
                    .values(status='closed', is_active=False)  # FIXED: Use status field
                )
                await session.commit()

            embed = discord.Embed(
                title="🔒 Poll Closed",
                description=f"Poll #{poll_id} has been closed successfully.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Poll Question",
                value=poll.question[:200] + ("..." if len(poll.question) > 200 else ""),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Try to update the original poll message
            try:
                if poll.message_id and poll.channel_id:
                    channel = interaction.guild.get_channel(poll.channel_id)
                    if channel:
                        message = await channel.fetch_message(poll.message_id)

                        # Update embed to show closed status
                        if message.embeds:
                            embed = message.embeds[0]
                            embed.color = discord.Color.red()
                            embed.title = "🔒 " + (embed.title or "Poll (Closed)")

                            # Add closed notice
                            embed.add_field(
                                name="Status",
                                value="This poll has been closed by an administrator.",
                                inline=False
                            )

                            # Disable all components
                            view = discord.ui.View()
                            await message.edit(embed=embed, view=view)
            except (discord.NotFound, discord.HTTPException):
                # Original message might be deleted, that's okay
                pass

        except (AttributeError, TypeError, ValueError) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to close poll: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Discord Error",
                description=f"Failed to close poll: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="list-polls", description="List recent polls in this server")
    async def list_polls(self, interaction: discord.Interaction):
        """List recent polls for this server."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Poll)
                    .where(Poll.guild_id == interaction.guild_id)
                    .order_by(Poll.created_at.desc())
                    .limit(10)
                )
                polls = result.scalars().all()

            if not polls:
                embed = discord.Embed(
                    title="📊 No Polls Found",
                    description="No polls have been created in this server yet.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Create a Poll",
                    value="Use `/poll` to create your first poll!",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="📊 Recent Polls",
                description=f"Showing {len(polls)} most recent polls",
                color=discord.Color.blue()
            )

            for i, poll in enumerate(polls, 1):
                author = interaction.guild.get_member(poll.author_id)
                author_name = author.display_name if author else f"Unknown ({poll.author_id})"

                channel = interaction.guild.get_channel(poll.channel_id)
                channel_name = channel.mention if channel else f"#{poll.channel_id}"

                status_emoji = {
                    'active': '🟢',
                    'closed': '🔴',
                    'expired': '⏰'
                }.get(poll.status, '❓')  # FIXED: Use status field

                embed.add_field(
                    name=f"{i}. {status_emoji} {poll.question[:50]}{'...' if len(poll.question) > 50 else ''}",
                    value=(
                        f"**ID:** {poll.id}\n"
                        f"**Author:** {author_name}\n"
                        f"**Channel:** {channel_name}\n"
                        f"**Created:** {discord.utils.format_dt(poll.created_at, 'R')}\n"
                        f"**Status:** {poll.status.title()}"  # FIXED: Use status field
                    ),
                    inline=True
                )

            embed.add_field(
                name="💡 Commands",
                value=(
                    "• `/poll-status <id>` - View detailed poll results\n"
                    "• `/close-poll <id>` - Close an active poll (admin)\n"
                    "• `/poll` - Create a new poll"
                ),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except (AttributeError, TypeError, ValueError) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to list polls: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Discord Error",
                description=f"Failed to display polls: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="poll-creator", description="Show poll creation interface")
    async def poll_creator_interface(self, interaction: discord.Interaction):
        """Show the poll creation interface."""
        view = PollCreatorView()

        embed = discord.Embed(
            title="📊 Poll Creator",
            description="Create engaging polls for your community!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🎯 Features",
            value=(
                "• Up to 10 poll options\n"
                "• Anonymous or public voting\n"
                "• Customizable duration\n"
                "• Real-time results\n"
                "• Visual vote bars"
            ),
            inline=True
        )

        embed.add_field(
            name="⚙️ Settings",
            value=(
                "• Choose any text channel\n"
                "• Set poll duration (1-720 hours)\n"
                "• Toggle anonymous voting\n"
                "• Rich question formatting\n"
                "• Automatic closing"
            ),
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(Polls(bot))