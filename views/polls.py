"""
Poll creation and management views for the Guild Management Bot
"""
from datetime import datetime, timedelta
from typing import List

import discord
from sqlalchemy import select, and_, func

from database import Poll, PollVote, get_session


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
            style=discord.TextStyle.paragraph,
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
        self.clear_items()
        
        # Anonymous toggle
        anon_button = discord.ui.Button(
            label=f"Anonymous: {'ON' if self.is_anonymous else 'OFF'}",
            style=discord.ButtonStyle.success if self.is_anonymous else discord.ButtonStyle.secondary,
            emoji="🎭" if self.is_anonymous else "👤"
        )
        anon_button.callback = self.toggle_anonymous
        self.add_item(anon_button)
        
        # Duration selector
        duration_select = discord.ui.Select(
            placeholder=f"Duration: {self.duration_hours} hours",
            options=[
                discord.SelectOption(label="1 hour", value="1"),
                discord.SelectOption(label="6 hours", value="6"),
                discord.SelectOption(label="12 hours", value="12"),
                discord.SelectOption(label="24 hours", value="24", default=True),
                discord.SelectOption(label="48 hours", value="48"),
                discord.SelectOption(label="72 hours", value="72"),
                discord.SelectOption(label="1 week", value="168")
            ]
        )
        duration_select.callback = self.select_duration
        self.add_item(duration_select)
        
        # Channel selector
        channel_select = discord.ui.ChannelSelect(
            placeholder="Select channel to post poll...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )
        channel_select.callback = self.select_channel
        self.add_item(channel_select)
        
        # Create poll button (only if channel is selected)
        if self.target_channel:
            create_button = discord.ui.Button(
                label="Create Poll",
                style=discord.ButtonStyle.primary,
                emoji="📊"
            )
            create_button.callback = self.create_poll
            self.add_item(create_button)
    
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
        
        if self.target_channel:
            embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        embed.add_field(name="Duration", value=f"{self.duration_hours} hours", inline=True)
        embed.add_field(name="Anonymous", value="Yes" if self.is_anonymous else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_duration(self, interaction: discord.Interaction):
        """Select poll duration."""
        self.duration_hours = int(interaction.data['values'][0])
        self.update_buttons()
        
        embed = discord.Embed(
            title="📊 Poll Settings",
            description=f"**Question:** {self.question}\n\n**Options:**\n" + 
                       "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(self.options)),
            color=discord.Color.blue()
        )
        
        if self.target_channel:
            embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        embed.add_field(name="Duration", value=f"{self.duration_hours} hours", inline=True)
        embed.add_field(name="Anonymous", value="Yes" if self.is_anonymous else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_channel(self, interaction: discord.Interaction):
        """Select target channel."""
        channel_id = int(interaction.data['values'][0])

        channel = interaction.guild.get_channel(channel_id) \
                or await interaction.guild.fetch_channel(channel_id)

        self.target_channel = channel
        self.update_buttons()
        
        embed = discord.Embed(
            title="📊 Poll Settings",
            description=f"**Question:** {self.question}\n\n**Options:**\n" + 
                       "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(self.options)),
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        embed.add_field(name="Duration", value=f"{self.duration_hours} hours", inline=True)
        embed.add_field(name="Anonymous", value="Yes" if self.is_anonymous else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_poll(self, interaction: discord.Interaction):
        """Create and post the poll."""
        if not self.target_channel:
            await interaction.response.send_message(
                "Please select a channel first!",
                ephemeral=True
            )
            return
        
        # Check permissions
        channel = interaction.guild.get_channel(self.target_channel.id)
        if not channel:
            await interaction.response.send_message(
                "Selected channel not found!",
                ephemeral=True
            )
            return
        
        bot_permissions = channel.permissions_for(interaction.guild.me)
        if not (bot_permissions.send_messages and bot_permissions.embed_links):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"I don't have permission to send messages or embed links in {channel.mention}.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Calculate close time
        close_time = datetime.utcnow() + timedelta(hours=self.duration_hours)
        
        # Create poll in database
        async with get_session() as session:
            poll = Poll(
                guild_id=interaction.guild_id,
                channel_id=channel.id,
                author_id=interaction.user.id,
                question=self.question,
                options=self.options,
                is_anonymous=self.is_anonymous,
                closes_at=close_time
            )
            session.add(poll)
            await session.commit()
            await session.refresh(poll)
        
        # Create poll embed
        poll_embed = discord.Embed(
            title="📊 " + self.question,
            color=discord.Color.blue(),
            timestamp=close_time
        )
        
        poll_embed.add_field(
            name="Options",
            value="\n".join(f"{chr(127462 + i)} {opt}" for i, opt in enumerate(self.options)),
            inline=False
        )
        
        poll_embed.add_field(
            name="Settings",
            value=f"• **Anonymous:** {'Yes' if self.is_anonymous else 'No'}\n• **Duration:** {self.duration_hours} hours",
            inline=True
        )
        
        poll_embed.add_field(
            name="Votes",
            value="No votes yet",
            inline=True
        )
        
        poll_embed.set_footer(text="Poll closes at")
        poll_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        # Create poll view
        poll_view = PollVoteView(poll.id, self.options, self.is_anonymous)
        
        # Send poll to target channel
        try:
            poll_message = await channel.send(embed=poll_embed, view=poll_view)
            
            # Update poll with message ID
            async with get_session() as session:
                result = await session.execute(select(Poll).where(Poll.id == poll.id))
                poll = result.scalar_one()
                poll.message_id = poll_message.id
                await session.commit()
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Poll Created",
                description=f"Poll has been posted in {channel.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=f"{self.duration_hours} hours", inline=True)
            embed.add_field(name="Anonymous", value="Yes" if self.is_anonymous else "No", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Log action
            bot = interaction.client
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
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create poll: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)


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
                style=discord.ButtonStyle.secondary,
                custom_id=f"poll_vote_{poll_id}_{i}",
                row=i // 5
            )
            button.callback = lambda inter, idx=i: self.vote_option(inter, idx)
            self.add_item(button)
        
        # Add management buttons for admins
        if len(options) <= 15:  # Leave room for management buttons
            results_button = discord.ui.Button(
                label="View Results",
                style=discord.ButtonStyle.primary,
                emoji="📈",
                custom_id=f"poll_results_{poll_id}",
                row=4
            )
            results_button.callback = self.view_results
            self.add_item(results_button)
            
            close_button = discord.ui.Button(
                label="Close Poll",
                style=discord.ButtonStyle.danger,
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
            
            if poll.closes_at and datetime.utcnow() > poll.closes_at:
                await interaction.response.send_message("This poll has expired.", ephemeral=True)
                return
            
            # Check if user already voted
            result = await session.execute(
                select(PollVote).where(
                    and_(
                        PollVote.poll_id == self.poll_id,
                        PollVote.user_id == interaction.user.id
                    )
                )
            )
            existing_vote = result.scalar_one_or_none()
            
            if existing_vote:
                # Update existing vote
                existing_vote.option_index = option_index
                await session.commit()
                action = "updated"
            else:
                # Create new vote
                vote = PollVote(
                    poll_id=self.poll_id,
                    user_id=interaction.user.id,
                    option_index=option_index
                )
                session.add(vote)
                await session.commit()
                action = "recorded"
        
        # Send confirmation
        option_name = self.options[option_index]
        embed = discord.Embed(
            title="✅ Vote Recorded",
            description=f"Your vote for **{option_name}** has been {action}!",
            color=discord.Color.green()
        )
        
        if not self.is_anonymous:
            embed.set_footer(text="Your vote is public and visible in the results.")
        else:
            embed.set_footer(text="Your vote is anonymous.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Update poll message with new vote counts
        await self.update_poll_message(interaction)
    
    async def view_results(self, interaction: discord.Interaction):
        """View detailed poll results."""
        async with get_session() as session:
            result = await session.execute(select(Poll).where(Poll.id == self.poll_id))
            poll = result.scalar_one_or_none()
            
            if not poll:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            # Get vote counts
            result = await session.execute(
                select(PollVote.option_index, func.count(PollVote.id))
                .where(PollVote.poll_id == self.poll_id)
                .group_by(PollVote.option_index)
            )
            vote_counts = dict(result.all())
            
            # Get voter details if not anonymous
            voter_details = {}
            if not poll.is_anonymous:
                result = await session.execute(
                    select(PollVote.option_index, PollVote.user_id)
                    .where(PollVote.poll_id == self.poll_id)
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
                
                bar_length = 10
                filled_length = int(bar_length * count / max(vote_counts.values())) if vote_counts else 0
                bar = "█" * filled_length + "░" * (bar_length - filled_length)
                
                result_line = f"{chr(127462 + i)} **{option}**\n{bar} {count} votes ({percentage:.1f}%)"
                
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
        
        if poll.closes_at:
            if datetime.utcnow() < poll.closes_at:
                embed.add_field(name="Closes", value=discord.utils.format_dt(poll.closes_at, 'R'), inline=True)
            else:
                embed.add_field(name="Status", value="Expired", inline=True)
        
        author = interaction.guild.get_member(poll.author_id)
        if author:
            embed.set_author(name=f"Created by {author.display_name}", icon_url=author.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def close_poll(self, interaction: discord.Interaction):
        """Close the poll (admin only)."""
        from utils.permissions import PermissionChecker
        
        if not PermissionChecker.is_moderator(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "close polls",
                "Administrator, Manage Server, Manage Roles, Manage Messages, or Moderate Members"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Close the poll
        async with get_session() as session:
            result = await session.execute(select(Poll).where(Poll.id == self.poll_id))
            poll = result.scalar_one_or_none()
            
            if not poll:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            if poll.status == 'closed':
                await interaction.response.send_message("Poll is already closed.", ephemeral=True)
                return
            
            poll.status = 'closed'
            poll.closed_at = datetime.utcnow()
            await session.commit()
        
        # Update the poll message
        await self.update_poll_message(interaction, closed=True)
        
        # Send confirmation
        embed = discord.Embed(
            title="🔒 Poll Closed",
            description=f"The poll has been closed by {interaction.user.mention}.",
            color=discord.Color.orange()
        )
        
        # Log action
        bot = interaction.client
        await bot.log_action(
            interaction.guild_id,
            "Poll Closed",
            interaction.user,
            None,
            f"Closed poll: {poll.question[:100]}..."
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def update_poll_message(self, interaction: discord.Interaction, closed: bool = False):
        """Update the original poll message with current results."""
        try:
            async with get_session() as session:
                result = await session.execute(select(Poll).where(Poll.id == self.poll_id))
                poll = result.scalar_one_or_none()
                
                if not poll or not poll.message_id:
                    return
                
                # Get vote counts
                result = await session.execute(
                    select(PollVote.option_index, func.count(PollVote.id))
                    .where(PollVote.poll_id == self.poll_id)
                    .group_by(PollVote.option_index)
                )
                vote_counts = dict(result.all())
            
            total_votes = sum(vote_counts.values())
            
            # Get the original message
            channel = interaction.guild.get_channel(poll.channel_id)
            if not channel:
                return
            
            try:
                message = await channel.fetch_message(poll.message_id)
            except discord.NotFound:
                return
            
            # Update embed
            embed = message.embeds[0] if message.embeds else discord.Embed()
            
            # Update vote counts field
            if total_votes == 0:
                vote_text = "No votes yet"
            else:
                vote_lines = []
                for i, option in enumerate(poll.options):
                    count = vote_counts.get(i, 0)
                    percentage = (count / total_votes * 100) if total_votes > 0 else 0
                    vote_lines.append(f"{chr(127462 + i)} {count} ({percentage:.1f}%)")
                vote_text = "\n".join(vote_lines)
            
            # Find and update the votes field
            for i, field in enumerate(embed.fields):
                if field.name == "Votes":
                    embed.set_field_at(i, name="Votes", value=vote_text, inline=True)
                    break
            
            # Update title if closed
            if closed:
                embed.title = "🔒 " + poll.question + " (CLOSED)"
                embed.color = discord.Color.orange()
            
            # Update view if closed
            view = None if closed else self
            
            await message.edit(embed=embed, view=view)
            
        except Exception as e:
            # Silently fail - don't interrupt the user experience
            pass


class CreatePollFromMessage(discord.ui.View):
    """Context menu view for creating polls from messages."""
    
    def __init__(self, message_content: str):
        super().__init__(timeout=300)
        self.message_content = message_content
    
    @discord.ui.button(label="Create Poll", style=discord.ButtonStyle.primary, emoji="📊")
    async def create_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a poll using the message content as the question."""
        # Truncate message content for question
        question = self.message_content[:200] + "..." if len(self.message_content) > 200 else self.message_content
        
        modal = PollOptionsModal(question)
        await interaction.response.send_modal(modal)


class PollOptionsModal(discord.ui.Modal):
    """Modal for entering poll options when creating from message."""
    
    def __init__(self, question: str):
        super().__init__(title="Poll Options")
        self.question = question
        
        self.options_input = discord.ui.TextInput(
            label="Options (one per line)",
            placeholder="Option 1\nOption 2\nOption 3",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.options_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle options submission."""
        options_text = self.options_input.value.strip()
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
        
        # Open poll settings
        view = PollSettingsView(self.question, options)
        
        embed = discord.Embed(
            title="📊 Poll Settings",
            description=f"**Question:** {self.question}\n\n**Options:**\n" + 
                       "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options)),
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)