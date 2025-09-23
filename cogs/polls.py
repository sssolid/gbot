"""
Polls cog for the Guild Management Bot
"""
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_, func

from database import Poll, PollVote, get_session
from utils.permissions import PermissionChecker
from views.polls import PollBuilderModal


class PollsCog(commands.Cog):
    """Handles poll-related commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="poll", description="Create a new poll")
    async def create_poll(self, interaction: discord.Interaction):
        """Create a new poll."""
        # Check if user can create polls
        bot = interaction.client
        config_cache = getattr(bot, 'config_cache', None)
        
        if config_cache:
            poll_config = await config_cache.get_poll_config(interaction.guild_id)
            creator_roles = poll_config.get('creator_roles', [])
            
            if not PermissionChecker.can_create_polls(interaction.user, creator_roles):
                embed = PermissionChecker.get_permission_error_embed(
                    "create polls",
                    "Administrator, Manage Server, Manage Roles, or designated poll creator role"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        elif not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        modal = PollBuilderModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="poll_results", description="View detailed results for a poll")
    @app_commands.describe(poll_id="The ID of the poll to view")
    async def poll_results(self, interaction: discord.Interaction, poll_id: int):
        """View detailed poll results."""
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
            result = await session.execute(
                select(PollVote.option_index, func.count(PollVote.id))
                .where(PollVote.poll_id == poll_id)
                .group_by(PollVote.option_index)
            )
            vote_counts = dict(result.all())
            
            # Get voter details if not anonymous
            voter_details = {}
            if not poll.is_anonymous:
                result = await session.execute(
                    select(PollVote.option_index, PollVote.user_id)
                    .where(PollVote.poll_id == poll_id)
                )
                for option_idx, user_id in result.all():
                    if option_idx not in voter_details:
                        voter_details[option_idx] = []
                    voter_details[option_idx].append(user_id)
        
        total_votes = sum(vote_counts.values())
        
        embed = discord.Embed(
            title=f"📊 Poll Results: {poll.question}",
            color=discord.Color.blue()
        )
        
        if total_votes == 0:
            embed.description = "No votes have been cast yet."
        else:
            results = []
            for i, option in enumerate(poll.options):
                count = vote_counts.get(i, 0)
                percentage = (count / total_votes * 100) if total_votes > 0 else 0
                
                # Create visual bar
                bar_length = 10
                filled_length = int(bar_length * count / max(vote_counts.values())) if vote_counts else 0
                bar = "█" * filled_length + "░" * (bar_length - filled_length)
                
                result_line = f"{chr(127462 + i)} **{option}**\n{bar} {count} votes ({percentage:.1f}%)"
                
                # Add voter names if not anonymous
                if not poll.is_anonymous and i in voter_details:
                    voters = []
                    for user_id in voter_details[i][:5]:  # Show max 5 voters
                        user = interaction.guild.get_member(user_id)
                        if user:
                            voters.append(user.display_name)
                    
                    if voters:
                        voter_text = ", ".join(voters)
                        if len(voter_details[i]) > 5:
                            voter_text += f" +{len(voter_details[i]) - 5} more"
                        result_line += f"\n*{voter_text}*"
                
                results.append(result_line)
            
            embed.description = "\n\n".join(results)
        
        embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
        embed.add_field(name="Anonymous", value="Yes" if poll.is_anonymous else "No", inline=True)
        embed.add_field(name="Status", value=poll.status.title(), inline=True)
        
        if poll.closes_at:
            if datetime.utcnow() < poll.closes_at:
                embed.add_field(name="Closes", value=discord.utils.format_dt(poll.closes_at, 'R'), inline=True)
            else:
                embed.add_field(name="Closed", value=discord.utils.format_dt(poll.closes_at, 'R'), inline=True)
        
        author = interaction.guild.get_member(poll.author_id)
        if author:
            embed.set_author(name=f"Created by {author.display_name}", icon_url=author.display_avatar.url)
        
        embed.set_footer(text=f"Poll ID: {poll.id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="close_poll", description="Close an active poll (Admin/Moderator only)")
    @app_commands.describe(poll_id="The ID of the poll to close")
    async def close_poll(self, interaction: discord.Interaction, poll_id: int):
        """Close an active poll."""
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "close polls",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
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
            
            if poll.status == 'closed':
                embed = discord.Embed(
                    title="❌ Poll Already Closed",
                    description="This poll is already closed.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Close the poll
            poll.status = 'closed'
            poll.closed_at = datetime.utcnow()
            await session.commit()
        
        # Try to update the original poll message
        if poll.message_id:
            try:
                channel = interaction.guild.get_channel(poll.channel_id)
                if channel:
                    message = await channel.fetch_message(poll.message_id)
                    
                    # Update embed to show closed status
                    if message.embeds:
                        embed_data = message.embeds[0]
                        embed_data.title = "🔒 " + poll.question + " (CLOSED)"
                        embed_data.color = discord.Color.orange()
                        
                        await message.edit(embed=embed_data, view=None)
            except (discord.NotFound, discord.Forbidden):
                pass  # Message not found or no permissions
        
        embed = discord.Embed(
            title="🔒 Poll Closed",
            description=f"Poll '{poll.question}' has been closed.",
            color=discord.Color.orange()
        )
        
        # Log action
        await self.bot.log_action(
            interaction.guild_id,
            "Poll Closed",
            interaction.user,
            None,
            f"Closed poll: {poll.question[:100]}..."
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="my_polls", description="View polls you've created")
    async def my_polls(self, interaction: discord.Interaction):
        """View polls created by the user."""
        async with get_session() as session:
            result = await session.execute(
                select(Poll).where(
                    and_(
                        Poll.author_id == interaction.user.id,
                        Poll.guild_id == interaction.guild_id
                    )
                ).order_by(Poll.created_at.desc())
            )
            user_polls = result.scalars().all()
        
        if not user_polls:
            embed = discord.Embed(
                title="📊 Your Polls",
                description="You haven't created any polls yet. Use `/poll` to create one!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Your Polls",
            description=f"You have created {len(user_polls)} poll(s) in this server.",
            color=discord.Color.blue()
        )
        
        for poll in user_polls[:10]:  # Show up to 10 polls
            status_emoji = "🔒" if poll.status == 'closed' else "📊"
            
            # Get vote count
            async with get_session() as session:
                result = await session.execute(
                    select(func.count(PollVote.id))
                    .where(PollVote.poll_id == poll.id)
                )
                vote_count = result.scalar_one()
            
            embed.add_field(
                name=f"{status_emoji} {poll.question[:50]}{'...' if len(poll.question) > 50 else ''}",
                value=(
                    f"**Status:** {poll.status.title()}\n"
                    f"**Votes:** {vote_count}\n"
                    f"**Created:** {discord.utils.format_dt(poll.created_at, 'R')}\n"
                    f"**ID:** {poll.id}"
                ),
                inline=False
            )
        
        if len(user_polls) > 10:
            embed.add_field(
                name="",
                value=f"...and {len(user_polls) - 10} more poll(s)",
                inline=False
            )
        
        embed.set_footer(text="Use /poll_results <ID> to view detailed results")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="poll_list", description="List recent polls in this server")
    @app_commands.describe(
        status="Filter by poll status",
        limit="Number of polls to show (default: 10)"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Active", value="active"),
        app_commands.Choice(name="Closed", value="closed")
    ])
    async def poll_list(self, interaction: discord.Interaction, status: str = "all", limit: int = 10):
        """List recent polls in the server."""
        if limit > 25:
            limit = 25  # Discord embed field limit
        
        async with get_session() as session:
            query = select(Poll).where(Poll.guild_id == interaction.guild_id)
            
            if status != "all":
                query = query.where(Poll.status == status)
            
            result = await session.execute(
                query.order_by(Poll.created_at.desc()).limit(limit)
            )
            polls = result.scalars().all()
        
        if not polls:
            filter_text = f" ({status})" if status != "all" else ""
            embed = discord.Embed(
                title=f"📊 Server Polls{filter_text}",
                description=f"No{filter_text.lower()} polls found in this server.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        filter_text = f" ({status.title()})" if status != "all" else ""
        embed = discord.Embed(
            title=f"📊 Server Polls{filter_text}",
            description=f"Showing {len(polls)} recent poll(s).",
            color=discord.Color.blue()
        )
        
        for poll in polls:
            status_emoji = "🔒" if poll.status == 'closed' else "📊"
            
            # Get vote count
            async with get_session() as session:
                result = await session.execute(
                    select(func.count(PollVote.id))
                    .where(PollVote.poll_id == poll.id)
                )
                vote_count = result.scalar_one()
            
            author = interaction.guild.get_member(poll.author_id)
            author_name = author.display_name if author else f"User {poll.author_id}"
            
            embed.add_field(
                name=f"{status_emoji} {poll.question[:50]}{'...' if len(poll.question) > 50 else ''}",
                value=(
                    f"**Author:** {author_name}\n"
                    f"**Votes:** {vote_count}\n"
                    f"**Created:** {discord.utils.format_dt(poll.created_at, 'R')}\n"
                    f"**ID:** {poll.id}"
                ),
                inline=False
            )
        
        embed.set_footer(text="Use /poll_results <ID> to view detailed results")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(PollsCog(bot))