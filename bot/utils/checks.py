# File: utils/checks.py
# Location: /bot/utils/checks.py

import discord
from discord.ext import commands
from models import RoleTier, Member, ApplicationStatus
from utils.helpers import get_role_id, is_blacklisted
from database import db
import logging

logger = logging.getLogger(__name__)


async def has_role_tier(ctx, required_tier: RoleTier) -> bool:
    """Check if user has required role tier or higher"""
    if not ctx.guild:
        return False

    # Fallback: Allow Discord server administrators for admin commands
    # This allows initial setup before roles are configured
    if required_tier == RoleTier.ADMIN:
        if ctx.user.guild_permissions.administrator:
            return True

    # Get hierarchy mapping
    tier_hierarchy = {
        RoleTier.APPLICANT: 0,
        RoleTier.MEMBER: 1,
        RoleTier.MODERATOR: 2,
        RoleTier.ADMIN: 3
    }

    required_level = tier_hierarchy.get(required_tier, 0)

    # Check each tier from highest to lowest
    for tier in [RoleTier.ADMIN, RoleTier.MODERATOR, RoleTier.MEMBER, RoleTier.APPLICANT]:
        role_id = await get_role_id(ctx.guild.id, tier)
        if role_id:
            role = ctx.guild.get_role(role_id)
            if role and role in ctx.user.roles:
                user_level = tier_hierarchy.get(tier, 0)
                return user_level >= required_level

    return False


async def is_admin(ctx) -> bool:
    """Check if user is admin"""
    return await has_role_tier(ctx, RoleTier.ADMIN)


async def is_moderator(ctx) -> bool:
    """Check if user is moderator or higher"""
    # Discord administrators always have moderator permissions
    if ctx.guild and ctx.user.guild_permissions.administrator:
        return True
    return await has_role_tier(ctx, RoleTier.MODERATOR)


async def is_member(ctx) -> bool:
    """Check if user is member or higher"""
    return await has_role_tier(ctx, RoleTier.MEMBER)


async def check_blacklist(ctx) -> bool:
    """Check if user is NOT blacklisted"""
    if not ctx.guild:
        return True

    blacklisted = await is_blacklisted(ctx.guild.id, ctx.user.id)
    return not blacklisted


def require_admin():
    """Decorator to require admin role"""

    async def predicate(ctx):
        if not await is_admin(ctx):
            raise commands.MissingPermissions(['Admin role required'])
        return True

    return commands.check(predicate)


def require_moderator():
    """Decorator to require moderator role or higher"""

    async def predicate(ctx):
        if not await is_moderator(ctx):
            raise commands.MissingPermissions(['Moderator role required'])
        return True

    return commands.check(predicate)


def require_member():
    """Decorator to require member role or higher"""

    async def predicate(ctx):
        if not await is_member(ctx):
            raise commands.MissingPermissions(['Member role required'])
        return True

    return commands.check(predicate)


def require_not_blacklisted():
    """Decorator to ensure user is not blacklisted"""

    async def predicate(ctx):
        if not await check_blacklist(ctx):
            raise commands.CheckFailure('You are blacklisted from using this bot')
        return True

    return commands.check(predicate)


async def can_moderate_submission(guild_id: int, user_id: int, submission_id: int) -> bool:
    """Check if user can moderate a specific submission"""
    # Check if submission is already processed
    with db.session_scope() as session:
        from models import Submission
        submission = session.query(Submission).filter_by(id=submission_id).first()

        if not submission:
            return False

        # Can't moderate if already approved or rejected
        if submission.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]:
            return False

    return True