# File: cogs/logging.py
# Location: /bot/cogs/logging.py

import discord
from discord.ext import commands
import logging
import json
from datetime import datetime

from models import Guild, MessageLog, ProfileChangeLog, Configuration, ProfileChangeType, Member
from database import db
from utils.helpers import create_embed, get_channel_id

logger = logging.getLogger(__name__)


class LoggingCog(commands.Cog):
    """Handles message logging and profile change monitoring"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Log all messages"""
        if message.author.bot:
            return

        if not message.guild:
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=message.guild.id).first()
            if not guild:
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.message_logging_enabled:
                return

            # Prepare attachments
            attachments_json = None
            if message.attachments:
                attachments_json = json.dumps([att.url for att in message.attachments])

            # Prepare embeds
            embeds_json = None
            if message.embeds:
                embeds_json = json.dumps([{
                    'title': e.title,
                    'description': e.description,
                    'url': e.url
                } for e in message.embeds])

            msg_log = MessageLog(
                guild_id=guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                user_id=message.author.id,
                username=str(message.author),
                content=message.content,
                attachments=attachments_json,
                embeds=embeds_json,
                timestamp=message.created_at
            )
            session.add(msg_log)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions"""
        if message.author.bot:
            return

        if not message.guild:
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=message.guild.id).first()
            if not guild:
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.message_logging_enabled:
                return

            msg_log = session.query(MessageLog).filter_by(
                message_id=message.id
            ).first()

            if msg_log:
                msg_log.deleted = True
                msg_log.deleted_at = datetime.utcnow()
            else:
                # Message wasn't logged (maybe bot was offline), log it now as deleted
                attachments_json = None
                if message.attachments:
                    attachments_json = json.dumps([att.url for att in message.attachments])

                msg_log = MessageLog(
                    guild_id=guild.id,
                    channel_id=message.channel.id,
                    message_id=message.id,
                    user_id=message.author.id,
                    username=str(message.author),
                    content=message.content,
                    attachments=attachments_json,
                    deleted=True,
                    timestamp=message.created_at,
                    deleted_at=datetime.utcnow()
                )
                session.add(msg_log)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits"""
        if before.author.bot:
            return

        if not before.guild:
            return

        # Ignore if content didn't change (embed updates, etc)
        if before.content == after.content:
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=before.guild.id).first()
            if not guild:
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.message_logging_enabled:
                return

            msg_log = session.query(MessageLog).filter_by(
                message_id=before.id
            ).first()

            if msg_log:
                if not msg_log.original_content:
                    msg_log.original_content = msg_log.content
                msg_log.content = after.content
                msg_log.edited = True
                msg_log.edited_at = datetime.utcnow()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Monitor profile changes"""
        if before.bot:
            return

        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=before.guild.id).first()
            if not guild:
                return

            config = session.query(Configuration).filter_by(guild_id=guild.id).first()
            if not config or not config.profile_change_alerts_enabled:
                return

            member_record = session.query(Member).filter_by(
                guild_id=guild.id,
                user_id=before.id
            ).first()

            changes = []

            # Check avatar change
            if before.display_avatar.url != after.display_avatar.url:
                change = ProfileChangeLog(
                    guild_id=guild.id,
                    user_id=before.id,
                    change_type=ProfileChangeType.AVATAR,
                    old_value=before.display_avatar.url,
                    new_value=after.display_avatar.url
                )
                session.add(change)
                changes.append(change)

                if member_record:
                    member_record.last_avatar_url = after.display_avatar.url

            # Check name change
            if before.name != after.name:
                change = ProfileChangeLog(
                    guild_id=guild.id,
                    user_id=before.id,
                    change_type=ProfileChangeType.NAME,
                    old_value=before.name,
                    new_value=after.name
                )
                session.add(change)
                changes.append(change)

                if member_record:
                    member_record.last_display_name = after.name

            # Check nickname change
            if before.nick != after.nick and before.nick is not None:
                change = ProfileChangeLog(
                    guild_id=guild.id,
                    user_id=before.id,
                    change_type=ProfileChangeType.NICKNAME,
                    old_value=before.nick or "None",
                    new_value=after.nick or "None"
                )
                session.add(change)
                changes.append(change)

                if member_record:
                    member_record.last_nickname = after.nick

            session.commit()

            # Send alert to moderators
            if changes:
                await self._alert_profile_change(before.guild.id, before, after, changes)

    async def _alert_profile_change(
            self,
            guild_id: int,
            before: discord.Member,
            after: discord.Member,
            changes: list
    ):
        """Send profile change alert to moderators"""
        channel_id = await get_channel_id(guild_id, "moderator_queue")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="👤 Profile Change Detected",
            description=f"**User:** {after.mention} ({after.id})",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        for change in changes:
            if change.change_type == ProfileChangeType.AVATAR:
                embed.add_field(
                    name="🖼️ Avatar Changed",
                    value=f"[Old Avatar]({change.old_value}) → [New Avatar]({change.new_value})",
                    inline=False
                )
                embed.set_thumbnail(url=change.new_value)

            elif change.change_type == ProfileChangeType.NAME:
                embed.add_field(
                    name="📝 Username Changed",
                    value=f"`{change.old_value}` → `{change.new_value}`",
                    inline=False
                )

            elif change.change_type == ProfileChangeType.NICKNAME:
                # Only display if old nickname is not None (new join)
                if change.old_value:
                    embed.add_field(
                        name="🏷️ Nickname Changed",
                        value=f"`{change.old_value}` → `{change.new_value}`",
                        inline=False
                    )

        embed.set_footer(text="Review if changes violate server terms")

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LoggingCog(bot))