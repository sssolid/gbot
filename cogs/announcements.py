"""
Announcements cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select, and_
from typing import Optional
from datetime import datetime, timedelta

from database import Announcement, get_session
from views.announcements import AnnouncementModal, AnnouncementManagerView
from utils.permissions import PermissionChecker


class AnnouncementsCog(commands.Cog):
    """Handles announcement commands and scheduling."""
    
    def __init__(self, bot):
        self.bot = bot
        self.check_scheduled_announcements.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.check_scheduled_announcements.cancel()
    
    @app_commands.command(name="announce", description="Create an announcement (Admin only)")
    async def create_announcement(self, interaction: discord.Interaction):
        """Create a new announcement."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        modal = AnnouncementModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="announcements", description="Manage announcements (Admin only)")
    async def manage_announcements(self, interaction: discord.Interaction):
        """Open announcement management interface."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "manage announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = AnnouncementManagerView()
        await view.show_announcements(interaction)
    
    @app_commands.command(name="quick_announce", description="Quick announcement to current channel (Admin only)")
    @app_commands.describe(
        message="The announcement message",
        mention_everyone="Whether to mention @everyone"
    )
    async def quick_announce(
        self, 
        interaction: discord.Interaction, 
        message: str,
        mention_everyone: bool = False
    ):
        """Create a quick announcement in the current channel."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "create announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check permissions
        bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
        if not (bot_permissions.send_messages and bot_permissions.embed_links):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="I don't have permission to send messages or embed links in this channel.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create announcement embed
        announcement_embed = discord.Embed(
            title="📢 Server Announcement",
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        announcement_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        announcement_embed.set_footer(text=interaction.guild.name)
        
        # Prepare content with mentions if enabled
        message_content = "@everyone" if mention_everyone else ""
        
        try:
            # Send the announcement
            announcement_message = await interaction.channel.send(
                content=message_content,
                embed=announcement_embed
            )
            
            # Save to database
            async with get_session() as session:
                announcement = Announcement(
                    guild_id=interaction.guild_id,
                    author_id=interaction.user.id,
                    channel_id=interaction.channel.id,
                    message_id=announcement_message.id,
                    content=message,
                    posted_at=datetime.utcnow()
                )
                session.add(announcement)
                await session.commit()
            
            # Success message
            embed = discord.Embed(
                title="✅ Announcement Posted",
                description="Your announcement has been posted!",
                color=discord.Color.green()
            )
            
            # Log action
            await self.bot.log_action(
                interaction.guild_id,
                "Quick Announcement",
                interaction.user,
                None,
                f"Posted in {interaction.channel.mention}: {message[:100]}{'...' if len(message) > 100 else ''}"
            )
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to send messages in this channel.",
                color=discord.Color.red()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to post announcement: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="scheduled_announcements", description="View scheduled announcements (Admin only)")
    async def view_scheduled(self, interaction: discord.Interaction):
        """View all scheduled announcements."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view scheduled announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with get_session() as session:
            result = await session.execute(
                select(Announcement)
                .where(
                    and_(
                        Announcement.guild_id == interaction.guild_id,
                        Announcement.posted_at.is_(None),
                        Announcement.scheduled_for.isnot(None)
                    )
                )
                .order_by(Announcement.scheduled_for)
            )
            scheduled_announcements = result.scalars().all()
        
        if not scheduled_announcements:
            embed = discord.Embed(
                title="⏰ Scheduled Announcements",
                description="No announcements are currently scheduled.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏰ Scheduled Announcements",
            description=f"You have {len(scheduled_announcements)} scheduled announcement(s).",
            color=discord.Color.orange()
        )
        
        for announcement in scheduled_announcements[:10]:  # Show first 10
            channel = interaction.guild.get_channel(announcement.channel_id)
            channel_name = channel.mention if channel else f"Channel {announcement.channel_id}"
            
            embed.add_field(
                name=f"Scheduled for {discord.utils.format_dt(announcement.scheduled_for, 'R')}",
                value=(
                    f"**Channel:** {channel_name}\n"
                    f"**Content:** {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}\n"
                    f"**ID:** {announcement.id}"
                ),
                inline=False
            )
        
        if len(scheduled_announcements) > 10:
            embed.add_field(
                name="",
                value=f"...and {len(scheduled_announcements) - 10} more announcement(s)",
                inline=False
            )
        
        embed.set_footer(text="Announcements will be posted automatically at their scheduled time")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cancel_announcement", description="Cancel a scheduled announcement (Admin only)")
    @app_commands.describe(announcement_id="ID of the announcement to cancel")
    async def cancel_announcement(self, interaction: discord.Interaction, announcement_id: int):
        """Cancel a scheduled announcement."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "cancel announcements",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with get_session() as session:
            result = await session.execute(
                select(Announcement)
                .where(
                    and_(
                        Announcement.id == announcement_id,
                        Announcement.guild_id == interaction.guild_id,
                        Announcement.posted_at.is_(None)
                    )
                )
            )
            announcement = result.scalar_one_or_none()
            
            if not announcement:
                embed = discord.Embed(
                    title="❌ Announcement Not Found",
                    description=f"No scheduled announcement found with ID {announcement_id}.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Delete the announcement
            await session.delete(announcement)
            await session.commit()
        
        embed = discord.Embed(
            title="❌ Announcement Cancelled",
            description=f"Scheduled announcement (ID: {announcement_id}) has been cancelled.",
            color=discord.Color.red()
        )
        
        # Log action
        await self.bot.log_action(
            interaction.guild_id,
            "Announcement Cancelled",
            interaction.user,
            None,
            f"Cancelled scheduled announcement: {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="announcement_history", description="View recent announcements (Admin only)")
    @app_commands.describe(limit="Number of announcements to show")
    async def announcement_history(self, interaction: discord.Interaction, limit: int = 10):
        """View recent announcement history."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view announcement history",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if limit > 25:
            limit = 25  # Discord embed limit
        
        async with get_session() as session:
            result = await session.execute(
                select(Announcement)
                .where(
                    and_(
                        Announcement.guild_id == interaction.guild_id,
                        Announcement.posted_at.isnot(None)
                    )
                )
                .order_by(Announcement.posted_at.desc())
                .limit(limit)
            )
            announcements = result.scalars().all()
        
        if not announcements:
            embed = discord.Embed(
                title="📢 Announcement History",
                description="No announcements have been posted yet.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📢 Announcement History",
            description=f"Showing {len(announcements)} recent announcement(s).",
            color=discord.Color.blue()
        )
        
        for announcement in announcements:
            author = interaction.guild.get_member(announcement.author_id)
            author_name = author.display_name if author else f"User {announcement.author_id}"
            
            channel = interaction.guild.get_channel(announcement.channel_id)
            channel_name = channel.mention if channel else f"Channel {announcement.channel_id}"
            
            # Create jump link if message still exists
            jump_link = ""
            if announcement.message_id:
                jump_link = f"\n[Jump to message](https://discord.com/channels/{announcement.guild_id}/{announcement.channel_id}/{announcement.message_id})"
            
            embed.add_field(
                name=f"📢 {discord.utils.format_dt(announcement.posted_at, 'R')}",
                value=(
                    f"**Author:** {author_name}\n"
                    f"**Channel:** {channel_name}\n"
                    f"**Content:** {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}"
                    f"{jump_link}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @tasks.loop(minutes=1)
    async def check_scheduled_announcements(self):
        """Check for and post scheduled announcements."""
        try:
            current_time = datetime.utcnow()
            
            async with get_session() as session:
                result = await session.execute(
                    select(Announcement)
                    .where(
                        and_(
                            Announcement.posted_at.is_(None),
                            Announcement.scheduled_for.isnot(None),
                            Announcement.scheduled_for <= current_time
                        )
                    )
                )
                due_announcements = result.scalars().all()
                
                for announcement in due_announcements:
                    await self.post_scheduled_announcement(announcement)
                    
        except Exception as e:
            print(f"Error checking scheduled announcements: {e}")
    
    @check_scheduled_announcements.before_loop
    async def before_check_scheduled(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()
    
    async def post_scheduled_announcement(self, announcement: Announcement):
        """Post a scheduled announcement."""
        try:
            guild = self.bot.get_guild(announcement.guild_id)
            if not guild:
                return
            
            channel = guild.get_channel(announcement.channel_id)
            if not channel:
                # Channel no longer exists, mark as failed
                async with get_session() as session:
                    result = await session.execute(
                        select(Announcement).where(Announcement.id == announcement.id)
                    )
                    db_announcement = result.scalar_one()
                    await session.delete(db_announcement)
                    await session.commit()
                return
            
            # Create announcement embed
            author = guild.get_member(announcement.author_id)
            
            announcement_embed = discord.Embed(
                title="📢 Server Announcement",
                description=announcement.content,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            if author:
                announcement_embed.set_author(
                    name=author.display_name,
                    icon_url=author.display_avatar.url
                )
            
            announcement_embed.set_footer(text=guild.name)
            
            # Send the announcement
            message = await channel.send(embed=announcement_embed)
            
            # Update database
            async with get_session() as session:
                result = await session.execute(
                    select(Announcement).where(Announcement.id == announcement.id)
                )
                db_announcement = result.scalar_one()
                db_announcement.message_id = message.id
                db_announcement.posted_at = datetime.utcnow()
                db_announcement.scheduled_for = None
                await session.commit()
            
            # Log action
            await self.bot.log_action(
                guild.id,
                "Scheduled Announcement Posted",
                author if author else guild.me,
                None,
                f"Posted in {channel.mention}: {announcement.content[:100]}{'...' if len(announcement.content) > 100 else ''}"
            )
            
        except discord.Forbidden:
            # No permission to send, remove from queue
            async with get_session() as session:
                result = await session.execute(
                    select(Announcement).where(Announcement.id == announcement.id)
                )
                db_announcement = result.scalar_one()
                await session.delete(db_announcement)
                await session.commit()
        except Exception as e:
            print(f"Error posting scheduled announcement {announcement.id}: {e}")


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(AnnouncementsCog(bot))