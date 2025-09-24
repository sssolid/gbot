"""
Poll creation and management views for the Guild Management Bot - FIXED VERSION
"""
import datetime
from typing import List
from datetime import timezone

import discord
from sqlalchemy import select, and_, func, update, delete
from discord.ext import commands

from database import Poll, PollVote, get_session
from utils.permissions import PermissionChecker


class PollBuilderModal(discord.ui.Modal):
    """Modal for creating polls."""

    def __init__(self):
        super().__init__(title="Create Poll")

        self.question_input = discord.ui.TextInput(
            label="Poll Question",
            placeholder="What would you like to ask?",
            required=True,
            max_length=500
        )
        self.add_item(self.question_input)

        self.options_input = discord.ui.TextInput(
            label="Options (one per line)",
            placeholder="Option 1\nOption 2\nOption 3",
            style=discord.TextStyle.paragraph, # type: ignore[arg-type]
            required=True,
            max_length=1000
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle poll creation submission."""
        question = self.question_input.value.strip()
        options_text = self.options_input.value.strip()

        # Parse options
        options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]

        if len(options) < 2:
            embed = discord.Embed(
                title="❌ Invalid Options",
                description="You must provide at least 2 options for the poll.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if len(options) > 10:
            embed = discord.Embed(
                title="❌ Too Many Options",
                description="You can have a maximum of 10 options for a poll.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Open poll settings view
        view = PollSettingsView(question, options)

        embed = discord.Embed(
            title="📊 Poll Settings",
            description=f"**Question:** {question}\n\n**Options:**\n" +
                       "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options)),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PollSettingsView(discord.ui.View):
    """View for configuring poll settings."""

    def __init__(self, question: str, options: List[str]):
        super().__init__(timeout=300)
        self.question = question
        self.options = options
        self.is_anonymous = False
        self.duration_hours = 24
        self.target_channel = None

        self.update_buttons()

    def update_buttons(self):
        """Update buttons based on current settings."""
        # Clear existing buttons
        self.clear_items()

        # Anonymous toggle
        self.add_item(discord.ui.Button(
            label=f"Anonymous: {'On' if self.is_anonymous else 'Off'}",
            style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
            emoji="👤",
            custom_id="toggle_anonymous"
        ))

        # Duration setting
        self.add_item(discord.ui.Button(
            label=f"Duration: {self.duration_hours}h",
            style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
            emoji="⏰",
            custom_id="set_duration"
        ))

        # Channel selection
        channel_label = f"Channel: #{self.target_channel.name}" if self.target_channel else "Select Channel"
        self.add_item(discord.ui.Button(
            label=channel_label,
            style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
            emoji="📝",
            custom_id="select_channel"
        ))

        # Create poll button
        self.add_item(discord.ui.Button(
            label="Create Poll",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="✅",
            custom_id="create_poll",
            disabled=self.target_channel is None
        ))

        # Set callbacks
        for item in self.children:
            if hasattr(item, 'custom_id'):
                if item.custom_id == "toggle_anonymous":
                    item.callback = self.toggle_anonymous
                elif item.custom_id == "set_duration":
                    item.callback = self.set_duration
                elif item.custom_id == "select_channel":
                    item.callback = self.select_channel
                elif item.custom_id == "create_poll":
                    item.callback = self.create_poll

    async def toggle_anonymous(self, interaction: discord.Interaction):
        """Toggle anonymous voting."""
        self.is_anonymous = not self.is_anonymous
        self.update_buttons()

        embed = discord.Embed(
            title="📊 Poll Settings",
            description=f"**Question:** {self.question}\n\n**Options:**\n" +
                       "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(self.options)),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Settings",
            value=(
                f"**Anonymous:** {'Yes' if self.is_anonymous else 'No'}\n"
                f"**Duration:** {self.duration_hours} hours\n"
                f"**Channel:** {self.target_channel.mention if self.target_channel else 'Not selected'}"
            ),
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def set_duration(self, interaction: discord.Interaction):
        """Set poll duration."""
        modal = PollDurationModal(self.duration_hours)
        modal.settings_view = self
        await interaction.response.send_modal(modal)

    async def select_channel(self, interaction: discord.Interaction):
        """Select target channel."""
        # Get text channels where user can send messages
        channels = [
            channel for channel in interaction.guild.text_channels
            if channel.permissions_for(interaction.user).send_messages
            and channel.permissions_for(interaction.guild.me).send_messages
        ]

        if not channels:
            embed = discord.Embed(
                title="❌ No Available Channels",
                description="No text channels available for creating polls.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=f"#{channel.name}",
                value=str(channel.id),
                description=channel.topic[:100] if channel.topic else "No description"
            )
            for channel in channels[:25]  # Discord limit
        ]

        select = discord.ui.Select(
            placeholder="Choose a channel for the poll...",
            options=options
        )
        select.callback = self.channel_selected

        view = discord.ui.View(timeout=300)
        view.add_item(select)

        await interaction.response.send_message("Select a channel:", view=view, ephemeral=True)

    async def channel_selected(self, interaction: discord.Interaction):
        """Handle channel selection."""
        channel_id = int(interaction.data['values'][0])
        self.target_channel = interaction.guild.get_channel(channel_id)
        self.update_buttons()

        embed = discord.Embed(
            title="✅ Channel Selected",
            description=f"Poll will be created in {self.target_channel.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def create_poll(self, interaction: discord.Interaction):
        """Create the poll."""
        if not self.target_channel:
            await interaction.response.send_message("Please select a channel first.", ephemeral=True)
            return

        try:
            # Calculate end time
            ends_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=self.duration_hours)

            # Create poll in database
            async with get_session() as session:
                poll = Poll(
                    guild_id=interaction.guild_id,
                    channel_id=self.target_channel.id,
                    author_id=interaction.user.id,
                    question=self.question,
                    options=self.options,
                    is_anonymous=self.is_anonymous,
                    is_active=True,
                    status='active',  # FIXED: Use status field
                    ends_at=ends_at
                )
                session.add(poll)
                await session.commit()
                await session.refresh(poll)
                poll_id = poll.id

            # Create poll embed
            embed = discord.Embed(
                title="📊 " + self.question,
                description="Vote by clicking the buttons below!",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Poll Options",
                value="\n".join(f"{chr(127462 + i)} {opt}" for i, opt in enumerate(self.options)),
                inline=False
            )

            embed.add_field(
                name="Settings",
                value=(
                    f"**Anonymous:** {'Yes' if self.is_anonymous else 'No'}\n"
                    f"**Ends:** {discord.utils.format_dt(ends_at, 'R')}"
                ),
                inline=False
            )

            embed.set_footer(text=f"Created by {interaction.user.display_name}")

            # Create voting view
            voting_view = PollVoteView(poll_id, self.options, self.is_anonymous)

            # Send poll to target channel
            channel = self.target_channel
            message = await channel.send(embed=embed, view=voting_view)

            # Update poll with message ID
            async with get_session() as session:
                await session.execute(
                    update(Poll).where(Poll.id == poll_id).values(message_id=message.id)
                )
                await session.commit()

            # Success response
            embed = discord.Embed(
                title="✅ Poll Created",
                description=f"Your poll has been created in {channel.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=f"{self.duration_hours} hours", inline=True)
            embed.add_field(name="Anonymous", value="Yes" if self.is_anonymous else "No", inline=True)

            await interaction.response.edit_message(embed=embed, view=None)

            # Log action
            bot = interaction.client
            if hasattr(bot, 'log_action'):
                await bot.log_action(
                    interaction.guild_id,
                    "Poll Created",
                    interaction.user,
                    None,
                    f"Question: {self.question[:100]}... in {channel.mention}"
                )

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description=f"I don't have permission to send messages in {channel.mention}.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create poll: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)


class PollDurationModal(discord.ui.Modal):
    """Modal for setting poll duration."""

    def __init__(self, current_hours: int):
        super().__init__(title="Set Poll Duration")
        self.settings_view = None

        self.hours_input = discord.ui.TextInput(
            label="Duration (hours)",
            placeholder="24",
            default=str(current_hours),
            required=True,
            min_length=1,
            max_length=4
        )
        self.add_item(self.hours_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle duration submission."""
        try:
            hours = int(self.hours_input.value)
            if hours < 1 or hours > 720:  # Max 30 days
                raise ValueError("Duration must be between 1 and 720 hours")

            if self.settings_view:
                self.settings_view.duration_hours = hours
                self.settings_view.update_buttons()

            embed = discord.Embed(
                title="✅ Duration Set",
                description=f"Poll duration set to {hours} hours",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description="Please enter a number between 1 and 720 hours.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class PollVoteView(discord.ui.View):
    """Persistent view for poll voting."""

    def __init__(self, poll_id: int, options: List[str], is_anonymous: bool):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.options = options
        self.is_anonymous = is_anonymous

        # Add option buttons (max 5 per row, max 25 total due to Discord limits)
        for i, option in enumerate(options[:20]):  # Limit to 20 options for safety
            button = discord.ui.Button(
                label=f"{chr(127462 + i)} {option[:50]}",  # Regional indicator emojis
                style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
                custom_id=f"poll_vote_{poll_id}_{i}",
                row=i // 5
            )
            button.callback = lambda inter, idx=i: self.vote_option(inter, idx)
            self.add_item(button)

        # Add management buttons for admins
        if len(options) <= 15:  # Leave room for management buttons
            results_button = discord.ui.Button(
                label="View Results",
                style=discord.ButtonStyle.primary, # type: ignore[arg-type]
                emoji="📈",
                custom_id=f"poll_results_{poll_id}",
                row=4
            )
            results_button.callback = self.view_results
            self.add_item(results_button)

            close_button = discord.ui.Button(
                label="Close Poll",
                style=discord.ButtonStyle.danger, # type: ignore[arg-type]
                emoji="🔒",
                custom_id=f"poll_close_{poll_id}",
                row=4
            )
            close_button.callback = self.close_poll
            self.add_item(close_button)

    async def vote_option(self, interaction: discord.Interaction, option_index: int):
        """Handle voting for an option."""
        # Check if poll is still active
        async with get_session() as session:
            result = await session.execute(select(Poll).where(Poll.id == self.poll_id))
            poll = result.scalar_one_or_none()

            if not poll:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return

            if poll.status != 'active':
                await interaction.response.send_message("This poll is no longer active.", ephemeral=True)
                return

            # Check if user has already voted
            existing_vote = await session.execute(
                select(PollVote).where(
                    and_(
                        PollVote.poll_id == self.poll_id,
                        PollVote.user_id == interaction.user.id
                    )
                )
            )
            existing_vote = existing_vote.scalar_one_or_none()

            if existing_vote:
                # Update existing vote
                await session.execute(
                    update(PollVote)
                    .where(PollVote.id == existing_vote.id)
                    .values(options=[option_index])
                )
                action = "updated"
            else:
                # Create new vote
                vote = PollVote(
                    poll_id=self.poll_id,
                    user_id=interaction.user.id,
                    options=[option_index]
                )
                session.add(vote)
                action = "recorded"

            await session.commit()

        # Response
        embed = discord.Embed(
            title="✅ Vote Recorded",
            description=f"Your vote for **{self.options[option_index]}** has been {action}!",
            color=discord.Color.green()
        )

        if not self.is_anonymous:
            embed.set_footer(text="This poll is not anonymous")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def view_results(self, interaction: discord.Interaction):
        """Show poll results."""
        async with get_session() as session:
            # Get poll info
            poll_result = await session.execute(select(Poll).where(Poll.id == self.poll_id))
            poll = poll_result.scalar_one_or_none()

            if not poll:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return

            # Get vote counts
            vote_counts = {}
            for i in range(len(poll.options)):
                count_result = await session.execute(
                    select(func.count(PollVote.id))
                    .where(
                        and_(
                            PollVote.poll_id == self.poll_id,
                            PollVote.options.contains([i])
                        )
                    )
                )
                vote_counts[i] = count_result.scalar() or 0

            total_votes = sum(vote_counts.values())

        # Create results embed
        embed = discord.Embed(
            title="📊 Poll Results",
            description=poll.question,
            color=discord.Color.blue()
        )

        results_text = []
        for i, option in enumerate(poll.options):
            count = vote_counts.get(i, 0)
            percentage = (count / total_votes * 100) if total_votes > 0 else 0

            # Create visual bar
            bar_length = 20
            filled = int(percentage / 100 * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)

            results_text.append(
                f"{chr(127462 + i)} **{option}**\n"
                f"`{bar}` {count} votes ({percentage:.1f}%)"
            )

        embed.add_field(
            name=f"Results ({total_votes} total votes)",
            value="\n\n".join(results_text),
            inline=False
        )

        # Show end time if active
        if poll.status == 'active' and poll.ends_at:
            embed.add_field(
                name="Status",
                value=f"Poll ends {discord.utils.format_dt(poll.ends_at, 'R')}",
                inline=False
            )
        elif poll.status != 'active':
            embed.add_field(
                name="Status",
                value="Poll closed",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def close_poll(self, interaction: discord.Interaction):
        """Close the poll (admin only)."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "close polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Close poll in database
            async with get_session() as session:
                await session.execute(
                    update(Poll)
                    .where(Poll.id == self.poll_id)
                    .values(status='closed', is_active=False)
                )
                await session.commit()

            embed = discord.Embed(
                title="🔒 Poll Closed",
                description="This poll has been closed by an administrator.",
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Disable all buttons
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True

            # Update original message
            try:
                await interaction.edit_original_response(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass  # Message might be deleted

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to close poll: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


# FIXED: Added missing PollManagerView
class PollManagerView(discord.ui.View):
    """Admin view for managing all polls."""

    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.polls: List[Poll] = []

    async def show_poll_manager(self, interaction: discord.Interaction):
        """Show the poll management interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage polls",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.load_polls(interaction.guild_id)
        embed = self._create_polls_embed(interaction)
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def load_polls(self, guild_id: int):
        """Load polls from database."""
        async with get_session() as session:
            result = await session.execute(
                select(Poll)
                .where(Poll.guild_id == guild_id)
                .order_by(Poll.created_at.desc())
                .limit(50)
            )
            self.polls = result.scalars().all()

    def _create_polls_embed(self, interaction: discord.Interaction):
        """Create embed showing polls."""
        embed = discord.Embed(
            title="📊 Poll Manager",
            description=f"Managing polls for {interaction.guild.name}",
            color=discord.Color.blue()
        )

        if not self.polls:
            embed.add_field(
                name="No Polls",
                value="No polls found in this server.",
                inline=False
            )
            return embed

        # Show polls (10 per page)
        start_idx = self.current_page * 10
        end_idx = min(start_idx + 10, len(self.polls))

        for i in range(start_idx, end_idx):
            poll = self.polls[i]
            author = interaction.guild.get_member(poll.author_id)
            author_name = author.display_name if author else f"Unknown ({poll.author_id})"
            channel = interaction.guild.get_channel(poll.channel_id)
            channel_name = channel.mention if channel else f"#{poll.channel_id}"

            status_emoji = {
                'active': '🟢',
                'closed': '🔴',
                'expired': '⏰'
            }.get(poll.status, '❓')

            embed.add_field(
                name=f"{status_emoji} {poll.question[:50]}{'...' if len(poll.question) > 50 else ''}",
                value=(
                    f"**Author:** {author_name}\n"
                    f"**Channel:** {channel_name}\n"
                    f"**Created:** {discord.utils.format_dt(poll.created_at, 'R')}\n"
                    f"**Status:** {poll.status.title()}"
                ),
                inline=True
            )

        embed.set_footer(
            text=f"Page {self.current_page + 1}/{(len(self.polls) - 1) // 10 + 1} • {len(self.polls)} total polls"
        )

        return embed

    @discord.ui.button(label="Previous Page", style=discord.ButtonStyle.secondary, emoji="⬅️") # type: ignore[arg-type]
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            embed = self._create_polls_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next Page", style=discord.ButtonStyle.secondary, emoji="➡️") # type: ignore[arg-type]
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        max_pages = (len(self.polls) - 1) // 10 + 1
        if self.current_page < max_pages - 1:
            self.current_page += 1
            embed = self._create_polls_embed(interaction)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄") # type: ignore[arg-type]
    async def refresh_polls(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the polls list."""
        await self.load_polls(interaction.guild_id)
        self.current_page = 0
        embed = self._create_polls_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Close Active Polls", style=discord.ButtonStyle.danger, emoji="🔒") # type: ignore[arg-type]
    async def close_active_polls(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close all active polls."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    update(Poll)
                    .where(
                        and_(
                            Poll.guild_id == interaction.guild_id,
                            Poll.status == 'active'
                        )
                    )
                    .values(status='closed', is_active=False)
                )
                closed_count = result.rowcount
                await session.commit()

            embed = discord.Embed(
                title="🔒 Polls Closed",
                description=f"Closed {closed_count} active poll(s).",
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Refresh the view
            await self.load_polls(interaction.guild_id)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to close polls: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Clean Old Polls", style=discord.ButtonStyle.secondary, emoji="🗑️") # type: ignore[arg-type]
    async def clean_old_polls(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clean up old polls (older than 30 days)."""
        try:
            cutoff_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)

            async with get_session() as session:
                # Delete old poll votes first (foreign key constraint)
                old_poll_ids = await session.execute(
                    select(Poll.id).where(
                        and_(
                            Poll.guild_id == interaction.guild_id,
                            Poll.created_at < cutoff_date,
                            Poll.status != 'active'
                        )
                    )
                )
                old_poll_ids = [row[0] for row in old_poll_ids]

                if old_poll_ids:
                    # Delete votes
                    await session.execute(
                        delete(PollVote).where(PollVote.poll_id.in_(old_poll_ids))
                    )

                    # Delete polls
                    result = await session.execute(
                        delete(Poll).where(Poll.id.in_(old_poll_ids))
                    )
                    deleted_count = result.rowcount
                    await session.commit()
                else:
                    deleted_count = 0

            embed = discord.Embed(
                title="🗑️ Old Polls Cleaned",
                description=f"Deleted {deleted_count} poll(s) older than 30 days.",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Refresh the view
            await self.load_polls(interaction.guild_id)

        except (discord.HTTPException, discord.DiscordException) as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to clean old polls: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class PollCreatorView(discord.ui.View):
    """Simple poll creation view for members."""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Create Poll", style=discord.ButtonStyle.primary, emoji="📊") # type: ignore[arg-type]
    async def create_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open poll creation modal."""
        # Check permissions
        from utils.cache import get_config

        try:
            bot = interaction.client
            config = await get_config(bot, interaction.guild_id, "poll_permissions", {})
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