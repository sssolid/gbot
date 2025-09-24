"""
Message logging cog for audit purposes - Enhanced logging system
"""
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands

from database import log_message_action, get_session


class MessageLoggingCog(commands.Cog):
    """Enhanced message logging for audit and moderation purposes."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Log message creation."""
        if not message.guild or message.author.bot:
            return

        # Check if logging is enabled for this guild
        if not await self.is_logging_enabled(message.guild.id):
            return

        await self.log_message(message, "created")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits."""
        if not before.guild or before.author.bot:
            return

        # Only log if content actually changed
        if before.content == after.content:
            return

        if not await self.is_logging_enabled(before.guild.id):
            return

        await self.log_message(after, "edited", original_content=before.content)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions."""
        if not message.guild or message.author.bot:
            return

        if not await self.is_logging_enabled(message.guild.id):
            return

        await self.log_message(message, "deleted")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Log bulk message deletions."""
        for message in messages:
            if message.guild and not message.author.bot:
                if await self.is_logging_enabled(message.guild.id):
                    await self.log_message(message, "bulk_deleted")

    @staticmethod
    async def is_logging_enabled(guild_id: int) -> bool:
        """Check if message logging is enabled for the guild."""
        # For now, logging is always enabled. Could be made configurable later.
        return True

    @staticmethod
    async def log_message(message: discord.Message, action: str, original_content: Optional[str] = None):
        """Log a message action to the database."""
        try:
            # Prepare attachment data
            attachments = []
            if message.attachments:
                for attachment in message.attachments:
                    attachments.append({
                        "filename": attachment.filename,
                        "url": attachment.url,
                        "size": attachment.size,
                        "content_type": attachment.content_type
                    })

            # Prepare embed data
            embeds = []
            if message.embeds:
                for embed in message.embeds:
                    embed_data = {
                        "title": embed.title,
                        "description": embed.description,
                        "url": embed.url,
                        "color": embed.color.value if embed.color else None,
                        "timestamp": embed.timestamp.isoformat() if embed.timestamp else None
                    }
                    embeds.append(embed_data)

            # Determine content to log
            content_to_log = message.content
            if action == "edited" and original_content is not None:
                content_to_log = f"BEFORE: {original_content}\nAFTER: {message.content}"

            await log_message_action(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                user_id=message.author.id,
                content=content_to_log,
                action=action,
                attachments=attachments if attachments else None,
                embeds=embeds if embeds else None
            )

        except Exception as e:
            print(f"Error logging message: {e}")

    @staticmethod
    async def get_message_history(guild_id: int, message_id: int) -> List[Dict[str, Any]]:
        """Get the full history of a message."""
        from database import MessageLog
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(MessageLog)
                .where(MessageLog.message_id == message_id)
                .order_by(MessageLog.created_at)
            )
            return [
                {
                    "action": log.action,
                    "content": log.content,
                    "attachments": log.attachments,
                    "embeds": log.embeds,
                    "timestamp": log.created_at,
                    "user_id": log.user_id
                }
                for log in result.scalars().all()
            ]

    @staticmethod
    async def search_messages(guild_id: int, user_id: Optional[int] = None,
                              channel_id: Optional[int] = None, content_search: Optional[str] = None,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Search message logs with various filters."""
        from database import MessageLog
        from sqlalchemy import select

        async with get_session() as session:
            query = select(MessageLog).where(MessageLog.guild_id == guild_id)

            if user_id:
                query = query.where(MessageLog.user_id == user_id)

            if channel_id:
                query = query.where(MessageLog.channel_id == channel_id)

            if content_search:
                query = query.where(MessageLog.content.contains(content_search))

            query = query.order_by(MessageLog.created_at.desc()).limit(limit)

            result = await session.execute(query)
            return [
                {
                    "message_id": log.message_id,
                    "channel_id": log.channel_id,
                    "user_id": log.user_id,
                    "content": log.content,
                    "action": log.action,
                    "timestamp": log.created_at,
                    "attachments": log.attachments,
                    "embeds": log.embeds
                }
                for log in result.scalars().all()
            ]


async def setup(bot):
    await bot.add_cog(MessageLoggingCog(bot))