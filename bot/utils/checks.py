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
    if required_tier in [RoleTier.SOVEREIGN, RoleTier.ADMIN]:
        if ctx.user.guild_permissions.administrator:
            return True

    # Get hierarchy mapping
    tier_hierarchy = {
        RoleTier.APPLICANT: 0,
        RoleTier.SQUIRE: 1,
        RoleTier.KNIGHT: 2,
        RoleTier.TEMPLAR: 3,
        RoleTier.SOVEREIGN: 4,
        # Legacy support
        RoleTier.MEMBER: 1,
        RoleTier.MODERATOR: 3,
        RoleTier.ADMIN: 4
    }

    required_level = tier_hierarchy.get(required_tier, 0)

    # Check each tier from highest to lowest
    tiers_to_check = [
        RoleTier.SOVEREIGN,
        RoleTier.TEMPLAR,
        RoleTier.KNIGHT,
        RoleTier.SQUIRE,
        RoleTier.APPLICANT,
        # Legacy tiers
        RoleTier.ADMIN,
        RoleTier.MODERATOR,
        RoleTier.MEMBER
    ]

    for tier in tiers_to_check:
        role_id = await get_role_id(ctx.guild.id, tier)
        if role_id:
            role = ctx.guild.get_role(role_id)
            if role and role in ctx.user.roles:
                user_level = tier_hierarchy.get(tier, 0)
                return user_level >= required_level

    return False


async def is_admin(ctx) -> bool:
    """Check if user is admin (Sovereign)"""
    return await has_role_tier(ctx, RoleTier.SOVEREIGN) or await has_role_tier(ctx, RoleTier.ADMIN)


async def is_moderator(ctx) -> bool:
    """Check if user is moderator (Templar) or higher"""
    # Discord administrators always have moderator permissions
    if ctx.guild and ctx.user.guild_permissions.administrator:
        return True

    # Check for Templar or higher
    if await has_role_tier(ctx, RoleTier.TEMPLAR):
        return True

    # Legacy support
    if await has_role_tier(ctx, RoleTier.MODERATOR):
        return True

    return False


async def is_member(ctx) -> bool:
    """Check if user is member (Squire) or higher"""
    # Check for Squire or higher
    if await has_role_tier(ctx, RoleTier.SQUIRE):
        return True

    # Legacy support
    if await has_role_tier(ctx, RoleTier.MEMBER):
        return True

    return False


async def is_knight(ctx) -> bool:
    """Check if user is Knight or higher"""
    return await has_role_tier(ctx, RoleTier.KNIGHT)


async def check_blacklist(ctx) -> bool:
    """Check if user is NOT blacklisted"""
    if not ctx.guild:
        return True

    blacklisted = await is_blacklisted(ctx.guild.id, ctx.user.id)
    return not blacklisted


def require_admin():
    """Decorator to require admin role (Sovereign)"""

    async def predicate(ctx):
        if not await is_admin(ctx):
            raise commands.MissingPermissions(['Sovereign/Admin role required'])
        return True

    return commands.check(predicate)


def require_moderator():
    """Decorator to require moderator role (Templar) or higher"""

    async def predicate(ctx):
        if not await is_moderator(ctx):
            raise commands.MissingPermissions(['Templar/Moderator role required'])
        return True

    return commands.check(predicate)


def require_member():
    """Decorator to require member role (Squire) or higher"""

    async def predicate(ctx):
        if not await is_member(ctx):
            raise commands.MissingPermissions(['Squire/Member role required'])
        return True

    return commands.check(predicate)


def require_knight():
    """Decorator to require Knight role or higher"""

    async def predicate(ctx):
        if not await is_knight(ctx):
            raise commands.MissingPermissions(['Knight role required'])
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