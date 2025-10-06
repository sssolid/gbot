# Discord Onboarding & Member Management Bot v2.0

A comprehensive Discord bot for automating member onboarding, application review, and character profile management with advanced moderation tools and logging capabilities.

## 🆕 What's New in v2.0

### User-Facing Features
- **🔄 Self-Service Reset** - Members can use `/reset` to restart their onboarding if something goes wrong
- **📢 Appeal System** - Rejected applicants can appeal decisions one time with `/appeal`
- **👤 Enhanced Profile Display** - Application reviews show full profile info (avatar, banner, account age)

### Moderator Tools
- **📊 Message Logging** - Complete message history including deleted/edited messages
- **🔍 Log Search** - Search through message logs with `/search_logs`
- **👁️ Profile Change Alerts** - Automatic notifications when users change avatars/names
- **🔄 Admin Reset** - Moderators can reset any user's onboarding with `/admin_reset_user`
- **🗑️ Strip Roles** - Remove all roles and reset status with `/admin_strip_roles`
- **💬 Bot Messaging** - Send DMs or channel messages through the bot
- **🖱️ Context Menus** - Right-click users for quick moderation actions
- **⏱️ Rate Limiting** - Automatic spam prevention for bot commands

## Features

- 🎯 **DM-Based Onboarding** - Private message onboarding flow with three paths
- 🔄 **Conditional Questions** - Dynamic follow-up questions based on previous answers
- 👥 **Moderation Workflow** - Streamlined review queue for moderators
- 🛡️ **Guild Role Hierarchy** - Sovereign, Templar, Knight, and Squire ranks
- 🎮 **Character Management** - Track game characters (Mortal Online 2 and more)
- 📢 **Bot-Managed Messages** - Welcome and rules messages managed by the bot
- ⚙️ **Fully Configurable** - Everything stored in database
- 🔒 **Role-Based Permissions** - Hierarchical permission system
- 📊 **Audit Logging** - Track all moderator actions
- 🚀 **PostgreSQL Ready** - SQLite by default, easy migration to PostgreSQL

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Migration from v1.0](#migration-from-v10)
- [New Features Guide](#new-features-guide)
- [Commands](#commands)
- [Operations Guide](#operations-guide)

## Requirements

- Python 3.9 or higher
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- SQLite (included with Python) or PostgreSQL (optional)

## Installation

### New Installation

```bash
# 1. Clone and setup
git clone <repository-url>
cd discord-onboarding-bot
./setup.sh

# 2. Configure environment
cp .env.example .env
nano .env  # Add DISCORD_TOKEN and GUILD_ID

# 3. Start bot
python bot/bot.py

# 4. Seed default data
python bot/seed_data.py YOUR_GUILD_ID

# 5. Configure in Discord
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_role role_tier:sovereign role:@GuildLeader
# ... (see QUICKSTART.md for full setup)
```

## Migration from v1.0

If you're upgrading from v1.0, run the migration script:

```bash
# Backup your database first!
cp bot.db bot.db.backup

# Run migration
python bot/migrate_v2.py

# Restart bot
python bot/bot.py
```

The migration adds:
- Message logging tables
- Profile change tracking
- Rate limiting system
- New columns for enhanced features

**Your existing data is safe** - the migration only adds new tables and columns.

## New Features Guide

### 1. User Reset Command

Members can reset their own onboarding process if they make a mistake or want to change their path (from Friend/Ally to full member, etc.).

**How it works:**
```
User: /reset
Bot: Shows confirmation with warning about role removal
User: Confirms
Bot: Deletes application, removes roles, restarts onboarding
```

**Restrictions:**
- Only available during IN_PROGRESS or PENDING status
- Rejected users can reset once
- Approved members with roles (except Squire/Friend) cannot reset
- Friends/Allies can reset to apply as full member (loses Squire role)

**User sees:**
```
⚠️ This will:
• Delete your current application
• Reset your status
• Remove your current role
• Allow you to start fresh

Are you sure?
```

### 2. Appeal System

Rejected applicants get ONE chance to appeal the decision.

**Process:**
```
1. User: /appeal
2. Bot: Opens modal "Why should we reconsider?"
3. User: Writes appeal explanation
4. Bot: Sends to moderator queue
5. Moderator: Reviews and approves or rejects with reason
6. User: Receives DM with decision
```

**Appeal Review UI:**
```
📢 Application Appeal
User: @Username

Appeal Reason:
[User's explanation]

[✅ Approve Appeal] [❌ Reject Appeal]
```

**Limitations:**
- Only ONE appeal allowed per rejection
- Appeal counter tracked in database
- Can only appeal if status is REJECTED

### 3. Enhanced Application Review

When moderators review applications, they now see:

**Profile Information:**
- 🖼️ Avatar (thumbnail + link)
- 🎨 Banner (full image if available)
- 👤 Display name
- 📅 Account creation date
- 🆔 User ID

This lets moderators spot potential issues immediately (inappropriate avatars, brand new accounts, etc.) without needing to manually check profiles.

### 4. Message Logging System

**Automatic logging of:**
- ✅ All messages sent in server
- ❌ Deleted messages (preserved in database)
- ✏️ Edited messages (original + new content saved)
- 📎 Attachments (URLs logged)
- 📋 Embeds (data logged)

**Moderator commands:**

```bash
# View last 10 messages from a user
/view_logs member:@User limit:10

# Search all messages for a term
/search_logs query:"inappropriate" member:@User

# Context menu: Right-click user → "View User Logs"
```

**What moderators see:**
```
📜 Message Logs - Username
Showing last 10 messages

#general - 2025-01-15 14:30 UTC ❌ [DELETED]
```
This was inappropriate content
```

#general - 2025-01-15 14:25 UTC ✏️ [EDITED]
```
Original message here
```
```

**Use cases:**
- User posts something against terms, then deletes it
- User claims they didn't say something
- Investigating harassment reports
- Pattern analysis for problematic behavior

### 5. Profile Change Monitoring

**Automatic alerts when users change:**
- 🖼️ Avatar
- 📝 Username
- 🏷️ Server nickname

**Moderator notification:**
```
👤 Profile Change Detected
User: @Username (ID: 12345)

🖼️ Avatar Changed
[Old Avatar] → [New Avatar]
(Thumbnails shown)

Review if changes violate server terms
```

**Why this matters:**
- User joins with appropriate avatar, then changes to inappropriate one
- User changes name to impersonate staff
- Tracking ban evaders who change identity
- Policy enforcement (profile content rules)

### 6. Advanced Moderator Commands

**Reset User's Onboarding**
```
/admin_reset_user member:@User
```
- Deletes all submissions/answers
- Resets status to IN_PROGRESS
- Removes current role
- Sends DM to user notifying them
- Logs action in audit trail

**Strip All Roles**
```
/admin_strip_roles member:@User reason:"Violated terms"
```
- Removes ALL guild roles (except @everyone)
- Resets database status
- Sends DM with reason
- Allows fresh start via /reset
- Logs action with reason

**Send DM Through Bot**
```
/admin_dm member:@User
```
Opens modal for message content. Useful for:
- Official warnings
- Policy clarifications  
- Appeal follow-ups
- Impersonal communication

**Send Message to Channel**
```
/admin_send channel:#announcements
```
Opens modal for title and content. Useful for:
- Official announcements
- Policy updates
- Bot-attributed messages
- Consistent formatting

### 7. Context Menu Commands

Right-click any user to access:
- **Reset User** - Quick access to admin reset
- **Strip Roles** - Quick role stripping (asks for reason)
- **DM User** - Send DM through bot
- **View User Logs** - See their message history

### 8. Rate Limiting

**Automatic spam prevention:**
- Tracks command usage per user
- Default: 5 uses per 5 minute window
- Applies to user-facing commands
- Prevents bot abuse/overload

**How it works:**
```python
# User tries command 6th time in 5 minutes
if rate_limited:
    return "⏱️ You're using commands too quickly. Please wait."
```

**Logged in database** for abuse pattern analysis.

## Commands

### Member Commands

| Command | Description | Rate Limited |
|---------|-------------|--------------|
| `/reset` | Reset your onboarding process | ✅ Yes |
| `/appeal` | Appeal a rejected application (one-time) | ✅ Yes |
| `/character_add` | Add a game character | ✅ Yes |
| `/character_list` | View your characters | ✅ Yes |
| `/character_remove` | Remove a character | ✅ Yes |

### Moderator Commands (Templar+)

| Command | Description |
|---------|-------------|
| `/queue` | View pending applications |
| `/review <id>` | Review specific application |
| `/promote <member> <tier>` | Promote member |
| `/demote <member> <tier>` | Demote member |
| `/admin_reset_user <member>` | Reset user's onboarding |
| `/admin_strip_roles <member> [reason]` | Strip all roles |
| `/admin_dm <member>` | Send DM through bot |
| `/admin_send <channel>` | Send message to channel |
| `/view_logs <member> [limit]` | View message logs |
| `/search_logs <query> [member]` | Search message logs |

### Context Menu (Right-Click)

**On Users:**
- Reset User
- Strip Roles  
- DM User
- View User Logs

### Admin Commands (Sovereign)

All previous admin commands remain:
- `/admin_help` - Command list
- `/set_channel` - Configure channels
- `/set_role` - Configure roles
- `/add_question` - Add question
- `/add_conditional_question` - Add follow-up
- `/set_welcome_message` - Set welcome
- `/set_rules_message` - Set rules
- `/view_config` - View configuration
- `/health` - Bot health status

## Operations Guide

### Daily Moderation Workflow

```
1. Check /queue for new applications
2. Right-click user → View User Logs (if suspicious)
3. /review <id> to see full application + profile
4. Check profile alerts in mod queue
5. Approve with role or reject with reason
```

### Handling Appeals

```
1. Appeal appears in mod queue with user's explanation
2. Review original rejection reason
3. Check if circumstances changed
4. [✅ Approve Appeal] - User can reapply
   OR
   [❌ Reject Appeal] - Provide clear reason
```

### Investigating Policy Violations

```
1. Receive report of inappropriate content
2. /view_logs member:@User
3. Check for deleted/edited messages
4. /search_logs query:"keyword" member:@User
5. Take appropriate action (warning, kick, ban)
```

### Profile Change Response

```
When alert appears:
1. Review old vs new avatar/name
2. Determine if violates policy
3. If violation:
   - /admin_dm to send warning
   - /admin_strip_roles if serious
   - Or ban if appropriate
```

### Resetting Problem Users

**Soft reset** (give another chance):
```
/admin_reset_user member:@User
```

**Hard reset** (serious violation):
```
/admin_strip_roles member:@User reason:"Policy violation - [details]"
```

### Rate Limit Abuse

If user is spamming commands:
- Rate limiter prevents excessive use automatically
- Check logs: `SELECT * FROM rate_limit_logs WHERE user_id = X`
- If malicious, consider timeout or ban

## Configuration

### Enable/Disable Logging

```sql
-- Disable message logging
UPDATE configurations SET message_logging_enabled = 0;

-- Disable profile change alerts
UPDATE configurations SET profile_change_alerts_enabled = 0;
```

### Adjust Rate Limits

Edit in code (`moderation_utils.py`):
```python
# Default: 5 uses per 5 minutes
await self.check_rate_limit(user_id, command, max_uses=5, window_minutes=5)
```

## Database Schema Changes

### New Tables

**message_logs**
- Stores all messages with deletion/edit tracking
- Indexed by message_id and user_id

**profile_change_logs**
- Tracks avatar, name, nickname changes
- Indexed by user_id

**rate_limit_logs**
- Command usage tracking
- Indexed by user_id

### New Columns

**members**
- `last_avatar_url` - Track avatar changes
- `last_display_name` - Track name changes
- `last_nickname` - Track nickname changes

**configurations**
- `message_logging_enabled` - Toggle message logging
- `profile_change_alerts_enabled` - Toggle profile alerts

**moderator_actions**
- Added `RESET` and `STRIP_ROLES` to ActionType enum

## Troubleshooting

### Migration Issues

```bash
# If migration fails
cp bot.db.backup bot.db
python bot/migrate_v2.py

# Check migration status
sqlite3 bot.db
.tables  # Should see message_logs, profile_change_logs, rate_limit_logs
```

### Message Logs Not Appearing

1. Check configuration:
   ```sql
   SELECT message_logging_enabled FROM configurations;
   ```

2. Verify bot has `Read Message History` permission

3. Check logs: `tail -f bot.log`

### Profile Changes Not Alerting

1. Check configuration:
   ```sql
   SELECT profile_change_alerts_enabled FROM configurations;
   ```

2. Verify moderator_queue channel is set

3. Bot needs `View Members` intent (should be enabled by default)

### Rate Limiting Too Strict

Adjust in `moderation_utils.py`:
```python
max_uses=10,  # Increase from 5
window_minutes=5
```

## Security Considerations

### Message Logging Privacy

- Logs contain user messages including deleted content
- Should comply with data retention policies
- Consider GDPR implications in EU
- Implement periodic cleanup if needed

### Access Control

- Only Templar+ can view message logs
- Only Sovereign+ can strip roles
- Context menus respect role hierarchy
- Rate limits prevent abuse

### Data Retention

Consider implementing:
```python
# Delete logs older than 90 days
DELETE FROM message_logs WHERE timestamp < datetime('now', '-90 days');
DELETE FROM profile_change_logs WHERE timestamp < datetime('now', '-90 days');
DELETE FROM rate_limit_logs WHERE timestamp < datetime('now', '-30 days');
```

## Best Practices

### For Administrators

1. **Regular log review** - Check for patterns of abuse
2. **Consistent appeals** - Have clear appeal criteria
3. **Document decisions** - Use reason fields thoroughly
4. **Privacy respect** - Don't abuse message logging
5. **Clear communication** - Use /admin_dm for formal warnings

### For Moderators

1. **Check logs first** - Before accusing, verify with /view_logs
2. **Context matters** - Read full conversation, not just flagged message
3. **Fair appeals** - Give benefit of doubt if circumstances changed
4. **Use reset wisely** - admin_reset_user is for genuine mistakes
5. **Document actions** - Always provide reason for strip_roles

## Performance

### Database Size

With logging enabled:
- ~1KB per message (text only)
- ~5KB per message (with attachments)
- High-traffic server (10K msgs/day) = ~5MB/day

**Recommendation:** Implement periodic cleanup of old logs

### Query Optimization

Indexes are already created on:
- message_logs(message_id, user_id)
- profile_change_logs(user_id)
- rate_limit_logs(user_id)

For high-volume servers, consider:
- PostgreSQL instead of SQLite
- Partitioning message_logs by month
- Archive old logs to separate table

## Advanced Usage

### Custom Alert Conditions

Edit `logging.py` to add custom profile change rules:

```python
# Alert only for new accounts
if (datetime.now() - member.created_at).days < 30:
    await self._alert_profile_change(...)
```

### Webhook Integration

Send logs to external service:

```python
# In logging.py on_message_delete
webhook_url = "https://your-service.com/webhook"
requests.post(webhook_url, json={
    'user_id': message.author.id,
    'content': message.content,
    'deleted_at': datetime.now()
})
```

### Analytics

Query message logs for insights:

```sql
-- Most active users
SELECT user_id, COUNT(*) as msg_count 
FROM message_logs 
WHERE deleted = 0 
GROUP BY user_id 
ORDER BY msg_count DESC 
LIMIT 10;

-- Deletion patterns
SELECT user_id, COUNT(*) as deleted_count
FROM message_logs
WHERE deleted = 1
GROUP BY user_id
HAVING deleted_count > 10;
```

## Roadmap

Future features being considered:
- 🔍 Advanced search with regex
- 📊 Analytics dashboard
- 🤖 Auto-moderation rules
- 📧 Email notifications for appeals
- 🔗 Integration with other bots
- 📱 Mobile app for moderation

## Support

For issues:
1. Check `bot.log` for errors
2. Use `/health` to verify setup
3. Review this documentation
4. Check Discord.py documentation

## Changelog

### v2.0 (2025-01-15)
- Added `/reset` command for users
- Added `/appeal` system for rejected applicants
- Enhanced application review with full profile display
- Added message logging system
- Added profile change monitoring
- Added advanced moderator commands
- Added context menu commands
- Added rate limiting
- Database migration system
- Performance optimizations

### v1.0 (Initial Release)
- DM-based onboarding
- Conditional questions
- Role hierarchy system
- Character management
- Bot-managed messages

## License

[Your license here]

## Credits

Built with:
- [discord.py](https://github.com/Rapptz/discord.py)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- Python 3.9+

---

**Version**: 2.0
**Last Updated**: January 2025