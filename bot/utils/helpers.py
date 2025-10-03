# File: utils/helpers.py
# Location: /bot/utils/helpers.py

import discord
from typing import Optional, List
from models import (
    Guild, Member, ChannelRegistry, RoleRegistry,
    ApplicationStatus, RoleTier
)
from database import db
import logging

logger = logging.getLogger(__name__)


async def get_or_create_guild(guild_id: int, guild_name: str = None) -> Guild:
    """Get or create guild record"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            guild = Guild(guild_id=guild_id, name=guild_name)
            session.add(guild)
            session.flush()
            logger.info(f"Created guild record for {guild_id}")
        return guild.id


async def get_or_create_member(guild_id: int, user_id: int, username: str = None) -> Member:
    """Get or create member record"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            return None

        member = session.query(Member).filter_by(
            guild_id=guild.id,
            user_id=user_id
        ).first()

        if not member:
            member = Member(
                guild_id=guild.id,
                user_id=user_id,
                username=username,
                status=ApplicationStatus.IN_PROGRESS
            )
            session.add(member)
            session.flush()
            logger.info(f"Created member record for user {user_id} in guild {guild_id}")

        return member


async def get_channel_id(guild_id: int, channel_type: str) -> Optional[int]:
    """Get configured channel ID by type"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            return None

        channel = session.query(ChannelRegistry).filter_by(
            guild_id=guild.id,
            channel_type=channel_type
        ).first()

        return channel.channel_id if channel else None


async def set_channel(guild_id: int, channel_type: str, channel_id: int) -> bool:
    """Set or update configured channel"""
    try:
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=guild_id).first()
            if not guild:
                return False

            channel = session.query(ChannelRegistry).filter_by(
                guild_id=guild.id,
                channel_type=channel_type
            ).first()

            if channel:
                channel.channel_id = channel_id
            else:
                channel = ChannelRegistry(
                    guild_id=guild.id,
                    channel_type=channel_type,
                    channel_id=channel_id
                )
                session.add(channel)

            logger.info(f"Set {channel_type} channel to {channel_id} for guild {guild_id}")
            return True
    except Exception as e:
        logger.error(f"Error setting channel: {e}")
        return False


async def get_role_id(guild_id: int, role_tier: RoleTier) -> Optional[int]:
    """Get configured role ID by tier"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            return None

        role = session.query(RoleRegistry).filter_by(
            guild_id=guild.id,
            role_tier=role_tier
        ).first()

        return role.role_id if role else None


async def set_role(guild_id: int, role_tier: RoleTier, role_id: int, hierarchy: int = 0) -> bool:
    """Set or update configured role"""
    try:
        with db.session_scope() as session:
            guild = session.query(Guild).filter_by(guild_id=guild_id).first()
            if not guild:
                return False

            role = session.query(RoleRegistry).filter_by(
                guild_id=guild.id,
                role_tier=role_tier
            ).first()

            if role:
                role.role_id = role_id
                role.hierarchy_level = hierarchy
            else:
                role = RoleRegistry(
                    guild_id=guild.id,
                    role_tier=role_tier,
                    role_id=role_id,
                    hierarchy_level=hierarchy
                )
                session.add(role)

            logger.info(f"Set {role_tier.value} role to {role_id} for guild {guild_id}")
            return True
    except Exception as e:
        logger.error(f"Error setting role: {e}")
        return False


async def create_embed(
        title: str,
        description: str = None,
        color: discord.Color = discord.Color.blue(),
        fields: List[tuple] = None,
        footer: str = None
) -> discord.Embed:
    """Create a standard embed"""
    embed = discord.Embed(title=title, description=description, color=color)

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    if footer:
        embed.set_footer(text=footer)

    return embed


async def try_send_dm(user: discord.User, content: str = None, embed: discord.Embed = None) -> bool:
    """Attempt to send a DM to a user"""
    try:
        await user.send(content=content, embed=embed)
        return True
    except discord.Forbidden:
        logger.warning(f"Cannot send DM to user {user.id} - DMs disabled")
        return False
    except Exception as e:
        logger.error(f"Error sending DM to user {user.id}: {e}")
        return False


async def is_blacklisted(guild_id: int, user_id: int) -> bool:
    """Check if user is blacklisted"""
    with db.session_scope() as session:
        guild = session.query(Guild).filter_by(guild_id=guild_id).first()
        if not guild:
            return False

        member = session.query(Member).filter_by(
            guild_id=guild.id,
            user_id=user_id
        ).first()

        return member.blacklisted if member else False


def chunk_list(lst: list, chunk_size: int) -> List[list]:
    """Split a list into chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]