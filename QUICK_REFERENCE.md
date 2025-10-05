# Admin Quick Reference - v2.0

## 🚀 Quick Setup (New Installation)

```bash
# 1. Install and configure
./setup.sh
nano .env  # Add DISCORD_TOKEN and GUILD_ID

# 2. Start bot
python bot/bot.py

# 3. Seed data
python bot/seed_data.py YOUR_GUILD_ID

# 4. Configure in Discord
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_channel channel_type:welcome channel:#welcome
/set_channel channel_type:rules channel:#rules

/set_role role_tier:sovereign role:@GuildLeader
/set_role role_tier:templar role:@Moderator
/set_role role_tier:knight role:@Knight
/set_role role_tier:squire role:@Member
/set_role role_tier:applicant role:@Applicant

/set_welcome_message
/set_rules_message
```

## 📋 Role Hierarchy

```
Sovereign (Guild Leader)  [Level 4] - Full control
    ↓
Templar (Moderator)      [Level 3] - Review apps, moderate
    ↓
Knight (Trusted Member)  [Level 2] - Special privileges
    ↓
Squire (Member)          [Level 1] - Approved member
    ↓
Applicant (Pending)      [Level 0] - Awaiting review
```

## 🎯 Onboarding Flow

```
Member Joins Server
    ↓
Receives DM with 3 Options:
    ├─ 🛡️ Apply to Join → Full application → APPLICANT role → Mod Queue
    ├─ 🤝 Friend/Ally → Info form → Mod Queue
    └─ 👤 Regular User → No onboarding → No special roles
         ↓
    Moderator Reviews
         ↓
    Approve with Role Selection OR Reject
         ↓
    Role Assigned + Announcement + DM Notification
```

## 🎮 Essential Commands

### Setup Commands
```
/admin_help                     - Show all admin commands
/view_config                    - View current setup
/health                         - Check bot status
```

### Channel Configuration
```
/set_channel channel_type:announcements channel:#channel
/set_channel channel_type:moderator_queue channel:#channel  
/set_channel channel_type:welcome channel:#channel
/set_channel channel_type:rules channel:#channel
```

### Role Configuration
```
/set_role role_tier:sovereign role:@Role
/set_role role_tier:templar role:@Role
/set_role role_tier:knight role:@Role
/set_role role_tier:squire role:@Role
/set_role role_tier:applicant role:@Role
```

### Questions
```
/add_question                   - Add main question
/add_conditional_question       - Add follow-up question
  parent_question_id:5
  parent_option_text:"Friend/Referral"
```

### Bot-Managed Messages
```
/set_welcome_message           - Create welcome message
/set_rules_message             - Create rules message
/update_welcome_message        - Update existing welcome
/update_rules_message          - Update existing rules
/set_welcome template:"..."    - Approval announcement template
```

### Games
```
/add_game game_name:"Game Name"
```

## 👮 Moderation Commands

### Review Queue
```
/queue                         - View all pending
/review submission_id:123      - Review specific app
```

### Member Management
```
/promote member:@User role_tier:knight
/demote member:@User role_tier:squire
```

### In Review UI
```
✅ Approve → Select Role (Sovereign/Templar/Knight/Squire)
❌ Reject → Reason → Reject Only / Reject & Ban
```

## 🔧 Common Admin Tasks

### Add a Conditional Question

**Example**: Ask for referrer name when user selects "Friend/Referral"

1. Note parent question ID (check /view_config or when created)
2. Run command:
   ```
   /add_conditional_question 
   parent_question_id:2 
   parent_option_text:"Friend/Referral"
   ```
3. Fill modal with follow-up question

### Update Welcome Message

```
/update_welcome_message
```

Edit the content in the modal, then it updates automatically.

### Promote a Member

```
/promote member:@Username role_tier:knight
```

This will:
- Remove old role (Squire)
- Add new role (Knight)
- Update database
- Post announcement

### Handle a Friend Request

1. Check `/queue` for friend requests (🤝 emoji)
2. `/review submission_id:123`
3. Read their info
4. Approve with appropriate role (usually Squire or Knight)

## ⚠️ Troubleshooting

### Members Not Getting DMs
- Member has DMs disabled
- Bot posts fallback in welcome channel
- Ask member to enable DMs and rejoin

### Roles Not Assigning
- Check bot role is **above** member roles in server settings
- Verify `/view_config` shows roles correctly
- Ensure bot has "Manage Roles" permission

### Conditional Questions Not Showing
- Verify exact option text matches: `parent_option_text:"Friend/Referral"`
- Check question is active: `/view_config`

### Application Not Starting
- Check member hasn't been blacklisted
- Verify they're clicking "Apply to Join" in DM
- Check bot logs for errors

## 📊 Best Practices

### Role Positioning (Server Settings → Roles)
```
Bot Role
────────
Sovereign
Templar
Knight
Squire
Applicant
────────
@everyone
```

### Channel Setup
- `#mod-queue`: Private, Templar+ only
- `#announcements`: Public, bot can post
- `#welcome`: Public, bot can post/manage messages
- `#rules`: Public, bot can post/manage messages

### Question Design
- Start with simple yes/no or single choice
- Use conditional questions for complex paths
- Mark deal-breakers with immediate_reject
- Keep text concise and clear

### Approval Workflow
- Squire: Default for new members
- Knight: For trusted/veteran members
- Templar: For staff/moderators only
- Sovereign: Guild leadership only

## 🎯 Quick Checks

**Daily**:
- [ ] Check `/queue` for pending apps
- [ ] Review any flagged applications

**Weekly**:
- [ ] `/health` - Verify bot status
- [ ] Check `bot.log` for errors
- [ ] Backup database: `cp bot.db bot.db.backup`

**Monthly**:
- [ ] Review questions - adjust as needed
- [ ] Update welcome/rules messages
- [ ] Promote active Squires to Knight

## 📱 Bot Permissions Checklist

Ensure bot has:
- [x] Manage Roles
- [x] Ban Members
- [x] Send Messages
- [x] Manage Messages
- [x] Embed Links
- [x] Use Slash Commands
- [x] View Channels
- [x] Read Message History

## 🆘 Emergency Commands

**Stop accepting applications**:
```sql
-- In database, deactivate all questions temporarily
UPDATE questions SET active = 0;
```

**Blacklist a user**:
Reject their application with ban option

**Reset a member's application**:
```sql
DELETE FROM submissions WHERE member_id = X;
UPDATE members SET status = 'IN_PROGRESS' WHERE id = X;
```

**View all Sovereign members**:
```sql
SELECT * FROM members WHERE role_tier = 'sovereign';
```

## 📞 Support Resources

- Logs: `tail -f bot.log`
- Health: `/health`
- Config: `/view_config`
- Database: SQLite browser or `sqlite3 bot.db`
- Docs: README.md

---

**Version**: 2.0 | **Updated**: 2025
**Role System**: Sovereign → Templar → Knight → Squire → Applicant