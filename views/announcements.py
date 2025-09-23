"""
Announcement system for the Guild Management Bot
"""
from datetime import datetime, timedelta

import discord
from sqlalchemy import select

from database import Announcement, get_session


class AnnouncementModal(discord.ui.Modal):
    """Modal for creating announcements."""
    
    def __init__(self):
        super().__init__(title="Create Announcement")
        
        self.content_input = discord.ui.TextInput(
            label="Announcement Content",
            placeholder="Enter your announcement text here...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        self.add_item(self.content_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle announcement creation."""
        content = self.content_input.value.strip()
        
        if not content:
            embed = discord.Embed(
                title="❌ Invalid Content",
                description="Announcement content cannot be empty.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Open announcement settings
        view = AnnouncementSettingsView(content)
        
        # Create preview embed
        preview_embed = discord.Embed(
            title="📢 Announcement Preview",
            description=content,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        preview_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        preview_embed.set_footer(text=f"{interaction.guild.name} • Preview")
        
        main_embed = discord.Embed(
            title="📢 Announcement Settings",
            description="Configure your announcement settings below:",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embeds=[main_embed, preview_embed], 
            view=view, 
            ephemeral=True
        )


class AnnouncementSettingsView(discord.ui.View):
    """View for configuring announcement settings."""
    
    def __init__(self, content: str):
        super().__init__(timeout=300)
        self.content = content
        self.target_channel = None
        self.schedule_delay = None
        self.mentions_enabled = False
        
        self.update_buttons()
    
    def update_buttons(self):
        """Update view buttons based on current settings."""
        self.clear_items()
        
        # Channel selector
        channel_select = discord.ui.ChannelSelect(
            placeholder="Select channel to post announcement...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )
        channel_select.callback = self.select_channel
        self.add_item(channel_select)
        
        # Schedule dropdown
        schedule_options = [
            discord.SelectOption(label="Post Now", value="now", description="Post immediately"),
            discord.SelectOption(label="5 minutes", value="5", description="Schedule for 5 minutes from now"),
            discord.SelectOption(label="15 minutes", value="15", description="Schedule for 15 minutes from now"),
            discord.SelectOption(label="1 hour", value="60", description="Schedule for 1 hour from now"),
            discord.SelectOption(label="2 hours", value="120", description="Schedule for 2 hours from now"),
            discord.SelectOption(label="24 hours", value="1440", description="Schedule for 24 hours from now")
        ]
        
        schedule_select = discord.ui.Select(
            placeholder=f"Timing: {'Now' if not self.schedule_delay else f'{self.schedule_delay} min'}",
            options=schedule_options
        )
        schedule_select.callback = self.select_schedule
        self.add_item(schedule_select)
        
        # Mentions toggle
        mentions_button = discord.ui.Button(
            label=f"@everyone: {'ON' if self.mentions_enabled else 'OFF'}",
            style=discord.ButtonStyle.success if self.mentions_enabled else discord.ButtonStyle.secondary,
            emoji="📣" if self.mentions_enabled else "🔇"
        )
        mentions_button.callback = self.toggle_mentions
        self.add_item(mentions_button)
        
        # Preview button
        preview_button = discord.ui.Button(
            label="Update Preview",
            style=discord.ButtonStyle.secondary,
            emoji="👁️"
        )
        preview_button.callback = self.update_preview
        self.add_item(preview_button)
        
        # Post button (only if channel is selected)
        if self.target_channel:
            post_button = discord.ui.Button(
                label="Post Announcement",
                style=discord.ButtonStyle.primary,
                emoji="📢"
            )
            post_button.callback = self.post_announcement
            self.add_item(post_button)
    
    async def select_channel(self, interaction: discord.Interaction):
        """Select target channel."""
        channel_id = int(interaction.data['values'][0])

        channel = interaction.guild.get_channel(channel_id) \
                or await interaction.guild.fetch_channel(channel_id)

        self.target_channel = channel
        self.update_buttons()
        
        embed = discord.Embed(
            title="📢 Announcement Settings",
            description="Configure your announcement settings below:",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        if self.schedule_delay:
            scheduled_time = datetime.utcnow() + timedelta(minutes=self.schedule_delay)
            embed.add_field(
                name="Scheduled For",
                value=discord.utils.format_dt(scheduled_time, 'F'),
                inline=True
            )
        else:
            embed.add_field(name="Timing", value="Post immediately", inline=True)
        
        embed.add_field(name="@everyone Mention", value="Yes" if self.mentions_enabled else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def select_schedule(self, interaction: discord.Interaction):
        """Select announcement schedule."""
        schedule_value = interaction.data['values'][0]
        
        if schedule_value == "now":
            self.schedule_delay = None
        else:
            self.schedule_delay = int(schedule_value)
        
        self.update_buttons()
        
        embed = discord.Embed(
            title="📢 Announcement Settings",
            description="Configure your announcement settings below:",
            color=discord.Color.blue()
        )
        
        if self.target_channel:
            embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        if self.schedule_delay:
            scheduled_time = datetime.utcnow() + timedelta(minutes=self.schedule_delay)
            embed.add_field(
                name="Scheduled For",
                value=discord.utils.format_dt(scheduled_time, 'F'),
                inline=True
            )
        else:
            embed.add_field(name="Timing", value="Post immediately", inline=True)
        
        embed.add_field(name="@everyone Mention", value="Yes" if self.mentions_enabled else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def toggle_mentions(self, interaction: discord.Interaction):
        """Toggle @everyone mentions."""
        self.mentions_enabled = not self.mentions_enabled
        self.update_buttons()
        
        embed = discord.Embed(
            title="📢 Announcement Settings",
            description="Configure your announcement settings below:",
            color=discord.Color.blue()
        )
        
        if self.target_channel:
            embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        if self.schedule_delay:
            scheduled_time = datetime.utcnow() + timedelta(minutes=self.schedule_delay)
            embed.add_field(
                name="Scheduled For", 
                value=discord.utils.format_dt(scheduled_time, 'F'),
                inline=True
            )
        else:
            embed.add_field(name="Timing", value="Post immediately", inline=True)
        
        embed.add_field(name="@everyone Mention", value="Yes" if self.mentions_enabled else "No", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def update_preview(self, interaction: discord.Interaction):
        """Update the preview embed."""
        # Create updated preview
        preview_embed = discord.Embed(
            title="📢 Server Announcement",
            description=self.content,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        preview_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        if self.target_channel:
            preview_embed.set_footer(text=f"{interaction.guild.name} • Will be posted in #{self.target_channel.name}")
        else:
            preview_embed.set_footer(text=f"{interaction.guild.name} • Select a channel")
        
        # Settings embed
        settings_embed = discord.Embed(
            title="📢 Announcement Settings",
            description="Configure your announcement settings below:",
            color=discord.Color.blue()
        )
        
        if self.target_channel:
            settings_embed.add_field(name="Target Channel", value=self.target_channel.mention, inline=True)
        
        if self.schedule_delay:
            scheduled_time = datetime.utcnow() + timedelta(minutes=self.schedule_delay)
            settings_embed.add_field(
                name="Scheduled For",
                value=discord.utils.format_dt(scheduled_time, 'F'),
                inline=True
            )
        else:
            settings_embed.add_field(name="Timing", value="Post immediately", inline=True)
        
        settings_embed.add_field(name="@everyone Mention", value="Yes" if self.mentions_enabled else "No", inline=True)
        
        await interaction.response.edit_message(embeds=[settings_embed, preview_embed], view=self)
    
    async def post_announcement(self, interaction: discord.Interaction):
        """Post the announcement."""
        if not self.target_channel:
            await interaction.response.send_message("Please select a channel first!", ephemeral=True)
            return
        
        # Check permissions
        channel = interaction.guild.get_channel(self.target_channel.id)
        if not channel:
            await interaction.response.send_message("Selected channel not found!", ephemeral=True)
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
        
        # Create the announcement
        if self.schedule_delay:
            # Schedule for later
            scheduled_time = datetime.utcnow() + timedelta(minutes=self.schedule_delay)
            
            async with get_session() as session:
                announcement = Announcement(
                    guild_id=interaction.guild_id,
                    author_id=interaction.user.id,
                    channel_id=channel.id,
                    content=self.content,
                    scheduled_for=scheduled_time
                )
                session.add(announcement)
                await session.commit()
            
            embed = discord.Embed(
                title="⏰ Announcement Scheduled",
                description=f"Your announcement has been scheduled to post in {channel.mention} at {discord.utils.format_dt(scheduled_time, 'F')}.",
                color=discord.Color.green()
            )
            
            # Note: In a real implementation, you'd want a task scheduler to handle delayed posts
            embed.add_field(
                name="⚠️ Note",
                value="Scheduled announcements require the bot to remain online. Consider posting immediately for important announcements.",
                inline=False
            )
            
        else:
            # Post immediately
            try:
                # Create announcement embed
                announcement_embed = discord.Embed(
                    title="📢 Server Announcement",
                    description=self.content,
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                announcement_embed.set_author(
                    name=interaction.user.display_name,
                    icon_url=interaction.user.display_avatar.url
                )
                announcement_embed.set_footer(text=interaction.guild.name)
                
                # Prepare content with mentions if enabled
                message_content = ""
                if self.mentions_enabled:
                    message_content = "@everyone"
                
                # Send the announcement
                announcement_message = await channel.send(
                    content=message_content,
                    embed=announcement_embed
                )
                
                # Save to database
                async with get_session() as session:
                    announcement = Announcement(
                        guild_id=interaction.guild_id,
                        author_id=interaction.user.id,
                        channel_id=channel.id,
                        message_id=announcement_message.id,
                        content=self.content,
                        posted_at=datetime.utcnow()
                    )
                    session.add(announcement)
                    await session.commit()
                
                # Success message
                embed = discord.Embed(
                    title="✅ Announcement Posted",
                    description=f"Your announcement has been posted in {channel.mention}!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Message Link",
                    value=f"[Jump to announcement]({announcement_message.jump_url})",
                    inline=False
                )
                
                # Log action
                bot = interaction.client
                await bot.log_action(
                    interaction.guild_id,
                    "Announcement Posted",
                    interaction.user,
                    None,
                    f"Posted in {channel.mention}: {self.content[:100]}{'...' if len(self.content) > 100 else ''}"
                )
                
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Permission Error",
                    description=f"I don't have permission to send messages in {channel.mention}.",
                    color=discord.Color.red()
                )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to post announcement: {str(e)}",
                    color=discord.Color.red()
                )
        
        await interaction.response.edit_message(embed=embed, view=None)


class AnnouncementManagerView(discord.ui.View):
    """View for managing existing announcements."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.announcements = []
    
    async def show_announcements(self, interaction: discord.Interaction):
        """Display announcement management interface."""
        await self.load_announcements(interaction.guild_id)
        
        embed = discord.Embed(
            title="📢 Announcement Manager",
            color=discord.Color.blue()
        )
        
        if not self.announcements:
            embed.description = "No announcements found."
        else:
            # Pagination
            per_page = 5
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_announcements = self.announcements[start_idx:end_idx]
            
            for announcement in page_announcements:
                author = interaction.guild.get_member(announcement.author_id)
                author_name = author.display_name if author else f"User {announcement.author_id}"
                
                channel = interaction.guild.get_channel(announcement.channel_id)
                channel_name = channel.mention if channel else f"Channel {announcement.channel_id}"
                
                status = "📤 Posted" if announcement.posted_at else "⏰ Scheduled"
                timestamp = announcement.posted_at or announcement.scheduled_for
                
                embed.add_field(
                    name=f"{status} - {discord.utils.format_dt(timestamp, 'R')}",
                    value=(
                        f"**Author:** {author_name}\n"
                        f"**Channel:** {channel_name}\n"
                        f"**Content:** {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page + 1} of {(len(self.announcements) - 1) // per_page + 1}")
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def load_announcements(self, guild_id: int):
        """Load announcements from database."""
        async with get_session() as session:
            # Load recent announcements (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await session.execute(
                select(Announcement)
                .where(Announcement.guild_id == guild_id)
                .where(Announcement.created_at >= thirty_days_ago)
                .order_by(Announcement.created_at.desc())
            )
            self.announcements = result.scalars().all()
    
    def update_buttons(self):
        """Update navigation and action buttons."""
        self.clear_items()
        
        # Create new announcement button
        create_button = discord.ui.Button(
            label="Create New",
            style=discord.ButtonStyle.primary,
            emoji="➕"
        )
        create_button.callback = self.create_new
        self.add_item(create_button)
        
        # Navigation buttons
        per_page = 5
        if self.current_page > 0:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if (self.current_page + 1) * per_page < len(self.announcements):
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Scheduled announcements management
        scheduled_count = sum(1 for a in self.announcements if not a.posted_at)
        if scheduled_count > 0:
            scheduled_button = discord.ui.Button(
                label=f"Manage Scheduled ({scheduled_count})",
                style=discord.ButtonStyle.secondary,
                emoji="⏰"
            )
            scheduled_button.callback = self.manage_scheduled
            self.add_item(scheduled_button)
    
    async def create_new(self, interaction: discord.Interaction):
        """Create a new announcement."""
        modal = AnnouncementModal()
        await interaction.response.send_modal(modal)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_announcements(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.announcements) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_announcements(interaction)
    
    async def manage_scheduled(self, interaction: discord.Interaction):
        """Manage scheduled announcements."""
        scheduled_announcements = [a for a in self.announcements if not a.posted_at]
        
        view = ScheduledAnnouncementsView(scheduled_announcements)
        
        embed = discord.Embed(
            title="⏰ Scheduled Announcements",
            description=f"You have {len(scheduled_announcements)} scheduled announcement(s).",
            color=discord.Color.orange()
        )
        
        for announcement in scheduled_announcements[:5]:  # Show first 5
            channel = interaction.guild.get_channel(announcement.channel_id)
            channel_name = channel.mention if channel else f"Channel {announcement.channel_id}"
            
            embed.add_field(
                name=f"Scheduled for {discord.utils.format_dt(announcement.scheduled_for, 'R')}",
                value=(
                    f"**Channel:** {channel_name}\n"
                    f"**Content:** {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ScheduledAnnouncementsView(discord.ui.View):
    """View for managing scheduled announcements."""
    
    def __init__(self, scheduled_announcements):
        super().__init__(timeout=300)
        self.scheduled_announcements = scheduled_announcements
        
        # Add dropdown for selecting scheduled announcements
        if scheduled_announcements and len(scheduled_announcements) <= 25:
            options = []
            for i, announcement in enumerate(scheduled_announcements):
                scheduled_time = discord.utils.format_dt(announcement.scheduled_for, 'f')
                content_preview = announcement.content[:50] + "..." if len(announcement.content) > 50 else announcement.content
                
                options.append(discord.SelectOption(
                    label=f"Scheduled for {scheduled_time}",
                    description=content_preview,
                    value=str(announcement.id)
                ))
            
            select = discord.ui.Select(
                placeholder="Select an announcement to manage...",
                options=options
            )
            select.callback = self.select_announcement
            self.add_item(select)
    
    async def select_announcement(self, interaction: discord.Interaction):
        """Select a scheduled announcement to manage."""
        announcement_id = int(interaction.data['values'][0])
        announcement = next((a for a in self.scheduled_announcements if a.id == announcement_id), None)
        
        if not announcement:
            await interaction.response.send_message("Announcement not found.", ephemeral=True)
            return
        
        view = SingleAnnouncementView(announcement)
        
        embed = discord.Embed(
            title="⏰ Scheduled Announcement",
            description=announcement.content,
            color=discord.Color.orange(),
            timestamp=announcement.scheduled_for
        )
        
        channel = interaction.guild.get_channel(announcement.channel_id)
        if channel:
            embed.add_field(name="Target Channel", value=channel.mention, inline=True)
        
        embed.add_field(
            name="Scheduled For",
            value=discord.utils.format_dt(announcement.scheduled_for, 'F'),
            inline=True
        )
        
        embed.set_footer(text="Scheduled for")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SingleAnnouncementView(discord.ui.View):
    """View for managing a single announcement."""
    
    def __init__(self, announcement):
        super().__init__(timeout=300)
        self.announcement = announcement
    
    @discord.ui.button(label="Post Now", style=discord.ButtonStyle.primary, emoji="📤")
    async def post_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Post the scheduled announcement immediately."""
        channel = interaction.guild.get_channel(self.announcement.channel_id)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="The target channel no longer exists.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Create and send announcement
            announcement_embed = discord.Embed(
                title="📢 Server Announcement",
                description=self.announcement.content,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            author = interaction.guild.get_member(self.announcement.author_id)
            if author:
                announcement_embed.set_author(
                    name=author.display_name,
                    icon_url=author.display_avatar.url
                )
            
            announcement_embed.set_footer(text=interaction.guild.name)
            
            message = await channel.send(embed=announcement_embed)
            
            # Update database
            async with get_session() as session:
                result = await session.execute(
                    select(Announcement).where(Announcement.id == self.announcement.id)
                )
                db_announcement = result.scalar_one()
                db_announcement.message_id = message.id
                db_announcement.posted_at = datetime.utcnow()
                db_announcement.scheduled_for = None
                await session.commit()
            
            embed = discord.Embed(
                title="✅ Announcement Posted",
                description=f"The announcement has been posted in {channel.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Message Link",
                value=f"[Jump to announcement]({message.jump_url})",
                inline=False
            )
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error", 
                description=f"I don't have permission to send messages in {channel.mention}.",
                color=discord.Color.red()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to post announcement: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_announcement(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the scheduled announcement."""
        # Delete from database
        async with get_session() as session:
            result = await session.execute(
                select(Announcement).where(Announcement.id == self.announcement.id)
            )
            db_announcement = result.scalar_one()
            await session.delete(db_announcement)
            await session.commit()
        
        embed = discord.Embed(
            title="❌ Announcement Cancelled",
            description="The scheduled announcement has been cancelled and removed.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)