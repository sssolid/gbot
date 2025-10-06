# v2.0 Feature Reference

Quick reference guide for all new features in Discord Onboarding Bot v2.0.

## 📋 Table of Contents

1. [User Self-Service Features](#user-self-service-features)
2. [Message Logging System](#message-logging-system)
3. [Profile Change Monitoring](#profile-change-monitoring)
4. [Advanced Moderation Tools](#advanced-moderation-tools)
5. [Context Menu Commands](#context-menu-commands)
6. [Rate Limiting](#rate-limiting)
7. [Enhanced Application Review](#enhanced-application-review)

---

## User Self-Service Features

### /reset Command

**Purpose:** Let users restart their onboarding process if something goes wrong.

**Availability:**
- ✅ Users with IN_PROGRESS application
- ✅ Users with PENDING application
- ✅ Users with REJECTED status
- ✅ Friends/Allies who want to apply as full member
- ❌ Fully approved members with high-tier roles

**What it does:**
1. Shows confirmation dialog with warning
2. Deletes all submissions and answers
3. Removes current role
4. Resets status to IN_PROGRESS
5. Sends new onboarding DM

**Example:**
```
User: /reset

Bot: ⚠️ Reset Onboarding Process

This will:
• Delete your current application
• Reset your status to 'In Progress'
• Remove your current role (Squire)
• Allow you to start fresh

[✅ Yes, Reset] [❌ Cancel]
```

**Use Cases:**
- User made mistake in application
- Friend wants to become full member
- User wants to change from Regular to Applicant
- Technical issue during application

### /appeal Command

**Purpose:** Give rejected applicants one chance to explain and request reconsideration.

**Limitations:**
- ONE appeal per user lifetime
- Only available if status = REJECTED
- Appeal counter tracked in database

**Process:**
1. User types `/appeal`
2. Modal opens: "Why should we reconsider?"
3. User writes explanation (up to 2000 chars)
4. Sent to moderator queue
5. Moderator reviews and approves/rejects
6. User receives DM with decision

**Moderator Review:**
```
📢 Application Appeal
User: @Username (ID: 12345)

Appeal Reason:
[User's explanation text]

[✅ Approve Appeal] [❌ Reject Appeal]
```

**If Approved:**
- Status reset to IN_PROGRESS
- Can reapply through normal process
- DM sent: "Good news! Your appeal has been approved..."

**If Rejected:**
- Moderator provides reason
- User cannot appeal again
- DM sent: "Your appeal has been reviewed and was not approved..."

---

## Message Logging System

### Automatic Logging

**What's Logged:**
- ✅ Every message sent in server
- ✅ Message content (text)
- ✅ Attachments (URLs preserved)
- ✅ Embeds (data preserved)
- ✅ Timestamp
- ✅ Channel and user info

**What's Tracked:**
- ❌ **Deleted messages** - Content preserved forever
- ✏️ **Edited messages** - Both original and new content saved
- 📎 **Attachments** - URLs logged even if deleted

**Database:**
```sql
message_logs table:
  - id (primary key)
  - guild_id
  - channel_id
  - message_id (indexed)
  - user_id (indexed)
  - username
  - content (original text)
  - attachments (JSON array)
  - embeds (JSON array)
  - deleted (boolean)
  - edited (boolean)
  - original_content (for edits)
  - timestamp
  - deleted_at
  - edited_at
```

### /view_logs Command

**Syntax:**
```
/view_logs member:@User limit:10
```

**Output:**
```
📜 Message Logs - Username
Showing last 10 messages

#general - 2025-01-15 14:30 UTC ❌ [DELETED]
```
This message was deleted
```

#general - 2025-01-15 14:25 UTC ✏️ [EDITED]
```
This is the edited version
```

#welcome - 2025-01-15 14:20 UTC
```
Regular message
```
```

**Parameters:**
- `member` - Required, which user to view
- `limit` - Optional, number of messages (default: 10, max: 50)

**Permissions:** Templar (Moderator) or higher

### /search_logs Command

**Syntax:**
```
/search_logs query:"inappropriate" member:@User
```

**Output:**
```
🔍 Search Results - 'inappropriate'
Found 3 messages

@User1 in #general - 2025-01-15 ❌ [DELETED]
```
Message containing 'inappropriate' content
```

@User2 in #offtopic - 2025-01-14
```
Another message with search term
```
```

**Parameters:**
- `query` - Required, search term (case-insensitive)
- `member` - Optional, filter by specific user

**Use Cases:**
- Find deleted messages about specific topic
- Investigate harassment reports
- Track pattern of problematic behavior
- Verify user's claim about what they said/didn't say

**Permissions:** Templar (Moderator) or higher

---

## Profile Change Monitoring

### What's Monitored

**Automatic detection of:**
- 🖼️ Avatar changes
- 📝 Username changes  
- 🏷️ Server nickname changes

**Database:**
```sql
profile_change_logs table:
  - id (primary key)
  - guild_id
  - user_id (indexed)
  - change_type (AVATAR, NAME, NICKNAME)
  - old_value (URL or text)
  - new_value (URL or text)
  - timestamp
  - notified (boolean)
```

**Also tracked in members table:**
- `last_avatar_url`
- `last_display_name`
- `last_nickname`

### Automatic Alerts

**Sent to:** Moderator queue channel

**Example Alert:**
```
👤 Profile Change Detected
User: @Username (ID: 123456789)

🖼️ Avatar Changed
[Old Avatar] → [New Avatar]
(Thumbnail shown)

Review if changes violate server terms

---

📝 Username Changed
`OldName#1234` → `NewName#5678`

---

🏷️ Nickname Changed
`OldNick` → `NewNick`
```

**Avatar changes:**
- Old and new avatars shown as thumbnail
- Links to full-size images provided

**Username changes:**
- Old and new names in monospace font
- Clear before/after display

**Nickname changes:**
- Shows "None" if nickname was removed
- Clear before/after display

### Use Cases

**Policy Enforcement:**
- User joins with appropriate avatar, changes to inappropriate
- User changes name to impersonate staff
- User changes name to evade search

**Ban Evasion:**
- Track patterns of identity changes
- Identify alt accounts by behavior

**Harassment:**
- User changes profile to harass others
- Impersonation attempts

**Response Actions:**
1. Review change in mod queue
2. Determine if violates policy
3. `/admin_dm @user` - Send warning
4. `/admin_strip_roles @user` - If serious
5. Or ban if appropriate

---

## Advanced Moderation Tools

### /admin_reset_user

**Purpose:** Reset a user's onboarding process (mod-initiated).

**Syntax:**
```
/admin_reset_user member:@User
```

**What it does:**
1. Deletes all submissions/answers
2. Resets status to IN_PROGRESS
3. Removes current role from database
4. Removes role from Discord
5. Logs action in moderator_actions
6. Sends DM to user notifying them
7. User can restart with fresh slate

**When to use:**
- User made genuine mistake
- Technical issue corrupted application
- Giving second chance after minor issue
- User requests restart and reason is valid

**Permissions:** Templar (Moderator) or higher

**User Notification:**
```
🔄 Onboarding Reset

A moderator has reset your onboarding process 
in ServerName.

You can now restart the application process. 
Check your DMs or use /reset in the server.
```

### /admin_strip_roles

**Purpose:** Remove all roles and reset user's status (severe action).

**Syntax:**
```
/admin_strip_roles member:@User reason:"Violated server terms"
```

**What it does:**
1. Removes ALL guild roles (except @everyone)
2. Deletes all submissions
3. Resets status to IN_PROGRESS
4. Resets role_tier to None
5. Logs action with reason
6. Sends DM with reason to user
7. Allows user to restart via /reset

**When to use:**
- Policy violation
- Inappropriate behavior
- Needs complete fresh start
- Demotion below Applicant

**Permissions:** Templar (Moderator) or higher

**User Notification:**
```
⚠️ Status Reset

Your status in ServerName has been reset 
by a moderator.

Reason: Violated server terms

All your roles have been removed. You can 
restart the onboarding process using /reset.
```

### /admin_dm

**Purpose:** Send direct message to user through the bot.

**Syntax:**
```
/admin_dm member:@User
```

Opens modal for message content.

**Modal:**
```
DM Username
├─ Message (text area, 2000 char max)
└─ [Submit]
```

**Message Format:**
```
Message from ServerName Moderators

[Your message content]

Sent by: ModeratorName
```

**When to use:**
- Official warnings
- Policy clarifications
- Appeal follow-ups
- Formal communication
- Impersonal messaging

**Advantages over personal DM:**
- Official server attribution
- Consistent formatting
- Logged in mod actions
- Professional appearance

**Permissions:** Templar (Moderator) or higher

### /admin_send

**Purpose:** Send message to channel through the bot.

**Syntax:**
```
/admin_send channel:#announcements
```

Opens modal for title and content.

**Modal:**
```
Send to #channel-name
├─ Title (optional, 256 char max)
├─ Message (text area, 2000 char max)
└─ [Submit]
```

**Output (with title):**
```
Embed:
  Title: Your Title
  Description: Your message content
  Color: Blue
```

**Output (without title):**
```
Plain message:
  Your message content
```

**When to use:**
- Official announcements
- Policy updates
- Bot-attributed messages
- Consistent formatting
- No personal attribution

**Permissions:** Templar (Moderator) or higher

---

## Context Menu Commands

### What are Context Menus?

Right-click menus on users in Discord for quick actions.

**How to access:**
1. Right-click user in member list
2. Select "Apps" submenu
3. Choose action

### Available Actions

#### Reset User
- Same as `/admin_reset_user`
- Quick access to reset function
- Requires Templar+ permissions

#### Strip Roles
- Same as `/admin_strip_roles`
- Opens modal for reason
- Requires Templar+ permissions

**Modal:**
```
Strip Roles - Username
├─ Reason (optional text area)
└─ [Submit]
```

#### DM User
- Same as `/admin_dm`
- Quick access to send DM
- Requires Templar+ permissions

#### View User Logs
- Same as `/view_logs member:@User`
- Shows last 10 messages
- Requires Templar+ permissions

### Advantages

**Speed:**
- No typing commands
- No remembering syntax
- Point and click

**Workflow:**
- Natural moderation flow
- Integrated with Discord UI
- Less context switching

**Accessibility:**
- Easier for new moderators
- Less training needed
- Discoverable interface

---

## Rate Limiting

### Purpose

Prevent bot abuse and spam by limiting command usage.

### How It Works

**Tracking:**
- Every command use logged in `rate_limit_logs`
- Includes user_id, command, timestamp

**Enforcement:**
- Default: 5 uses per 5 minute window
- Counts recent uses within window
- Blocks if limit exceeded
- Automatically cleans old logs

### Configuration

**Default Settings:**
```python
max_uses = 5
window_minutes = 5
```

**Commands affected:**
- `/reset`
- `/appeal`
- `/character_add`
- `/character_list`
- `/character_remove`

**Commands NOT affected:**
- Moderator commands
- Admin commands
- Context menu commands

### User Experience

**Normal use:**
```
User: /reset
Bot: [Shows reset confirmation]
```

**Rate limited:**
```
User: /reset (6th time in 5 minutes)
Bot: ⏱️ You're using commands too quickly. 
     Please wait a moment before trying again.
```

### Database

```sql
rate_limit_logs table:
  - id (primary key)
  - user_id (indexed)
  - command
  - timestamp
```

**Cleanup:**
```sql
-- Logs older than 30 minutes auto-cleaned
DELETE FROM rate_limit_logs 
WHERE timestamp < datetime('now', '-30 minutes');
```

### Adjusting Limits

Edit `moderation_utils.py`:

```python
# More strict
await self.check_rate_limit(
    user_id, 
    command, 
    max_uses=3,  # 3 instead of 5
    window_minutes=10  # 10 minutes instead of 5
)

# More lenient
await self.check_rate_limit(
    user_id, 
    command, 
    max_uses=10,  # 10 instead of 5
    window_minutes=5
)
```

---

## Enhanced Application Review

### Profile Information Display

When reviewing applications, moderators see:

**Standard Info:**
- Username and mention
- User ID
- Application answers
- Flag status

**NEW - Profile Info:**
- 🖼️ **Avatar** - Thumbnail + clickable link
- 🎨 **Banner** - Full image if available
- 👤 **Display Name** - Current display name
- 📅 **Account Created** - Creation date
- 🆔 **User ID** - In footer

### Example Review

```
📋 New Application

Applicant: @Username (Username#1234)
[Avatar thumbnail shown]

🖼️ Avatar: [View](https://cdn.discord.com/...)
🎨 Banner: [Full image displayed]
👤 Display Name: DisplayName
📅 Account Created: 2023-05-15

[All application Q&A displayed]

Submission ID: 123 | User ID: 987654321

[✅ Approve] [❌ Reject]
```

### Why This Matters

**Immediate Red Flags:**
- Inappropriate avatar
- Brand new account (created yesterday)
- Suspicious display name
- Banner with problematic content

**Better Decisions:**
- More context for approval
- Spot ban evaders
- Identify trolls
- Enforce profile policies

**Efficiency:**
- No need to manually check profiles
- All info in one place
- Faster review process
- Consistent information

### Friend/Ally Reviews

Same enhanced display:
```
🤝 New Friend/Ally Request

User: @Username
[Avatar and profile info displayed]

Information:
[Their explanation text]

[✅ Approve] [❌ Reject]
```

---

## Feature Summary Matrix

| Feature | User Access | Mod Access | Admin Access | Rate Limited |
|---------|-------------|------------|--------------|--------------|
| /reset | ✅ | ✅ | ✅ | ✅ |
| /appeal | ✅ | ✅ | ✅ | ✅ |
| /view_logs | ❌ | ✅ | ✅ | ❌ |
| /search_logs | ❌ | ✅ | ✅ | ❌ |
| /admin_reset_user | ❌ | ✅ | ✅ | ❌ |
| /admin_strip_roles | ❌ | ✅ | ✅ | ❌ |
| /admin_dm | ❌ | ✅ | ✅ | ❌ |
| /admin_send | ❌ | ✅ | ✅ | ❌ |
| Context Menus | ❌ | ✅ | ✅ | ❌ |
| Message Logging | Auto | View | View | N/A |
| Profile Monitoring | Auto | Alerts | Alerts | N/A |

---

## Configuration Options

All features can be toggled in database:

```sql
-- Disable message logging
UPDATE configurations 
SET message_logging_enabled = 0;

-- Disable profile change alerts
UPDATE configurations 
SET profile_change_alerts_enabled = 0;

-- Enable message logging
UPDATE configurations 
SET message_logging_enabled = 1;

-- Enable profile change alerts
UPDATE configurations 
SET profile_change_alerts_enabled = 1;
```

**Default:** All features enabled

---

## Privacy & Compliance

### GDPR Considerations

**Data Collected:**
- Message content (including deleted)
- Profile changes (avatar, name, nickname)
- Command usage logs
- User IDs

**User Rights:**
- Right to be forgotten
- Data export requests
- Data retention policies

**Recommendations:**
```sql
-- Implement periodic cleanup
DELETE FROM message_logs 
WHERE timestamp < datetime('now', '-90 days');

DELETE FROM profile_change_logs 
WHERE timestamp < datetime('now', '-90 days');
```

### Transparency

**Inform users:**
- Message logging in effect
- Deleted messages preserved
- Profile changes monitored
- Add to server rules/TOS

**Example rule:**
```
This server uses a moderation bot that:
• Logs all messages (including deleted)
• Monitors profile changes
• Tracks command usage
By participating, you consent to this monitoring.
```

---

## Performance Notes

### Database Growth

**With all features enabled:**
- ~1KB per message logged
- ~0.5KB per profile change
- ~0.1KB per rate limit log

**Example (medium server):**
- 1,000 messages/day = 1MB/day = 365MB/year
- 50 profile changes/day = 25KB/day = 9MB/year
- Rate limits: Negligible

**Large server (10K messages/day):**
- ~10MB/day = 3.6GB/year

**Recommendation:** Implement log rotation

### Query Performance

**Indexes created:**
- `message_logs(message_id)` - Fast lookup by message
- `message_logs(user_id)` - Fast user history
- `profile_change_logs(user_id)` - Fast user changes
- `rate_limit_logs(user_id)` - Fast rate checks

**Query times (SQLite):**
- View logs: <10ms
- Search logs: <50ms
- Profile lookup: <5ms
- Rate limit check: <5ms

**For high-volume servers:**
- Consider PostgreSQL
- Partition logs by month
- Archive old data

---

## Troubleshooting

### Message Logs Not Appearing

1. **Check config:**
   ```sql
   SELECT message_logging_enabled FROM configurations;
   ```

2. **Check permissions:**
   - Bot needs "Read Message History"

3. **Check intent:**
   - Message Content Intent enabled

4. **Check logs:**
   ```bash
   tail -f bot.log | grep -i message
   ```

### Profile Changes Not Alerting

1. **Check config:**
   ```sql
   SELECT profile_change_alerts_enabled FROM configurations;
   ```

2. **Check channel:**
   ```
   /view_config
   ```
   Verify moderator_queue is set

3. **Check intent:**
   - Server Members Intent enabled

### Rate Limiting Too Strict/Lenient

**Edit in** `moderation_utils.py`:
```python
# Line ~20
await self.check_rate_limit(
    user_id, 
    command, 
    max_uses=10,  # Adjust this
    window_minutes=5  # Adjust this
)
```

### Context Menus Not Showing

1. **Wait:** Discord takes 5-10 minutes to sync
2. **Restart:** Close and reopen Discord
3. **Permissions:** Check bot has app command permissions
4. **Re-sync:** Restart bot to force sync

---

## Best Practices

### For Administrators

1. **Document policies** - Clear rules about logging
2. **Train moderators** - Proper use of tools
3. **Review regularly** - Check for abuse patterns
4. **Retain appropriately** - Balance utility and privacy
5. **Transparent** - Inform users about monitoring

### For Moderators

1. **Use logs responsibly** - Don't abuse access
2. **Provide context** - Check full conversation
3. **Document actions** - Always provide reasons
4. **Fair appeals** - Consider changed circumstances
5. **Protect privacy** - Don't share logs publicly

### For Users

1. **Think before posting** - Logs are permanent
2. **Use /reset wisely** - Not for gaming the system
3. **Honest appeals** - Explain genuine circumstances
4. **Profile appropriate** - Changes are monitored
5. **Respect limits** - Don't spam commands

---

**Version:** 2.0  
**Last Updated:** January 2025

For complete documentation, see README_V2.md