# Discord Onboarding & Member Management Bot

A comprehensive Discord bot for automating member onboarding, application review, and character profile management. Built with Python, discord.py, and SQLAlchemy.

## Features

- 🎯 **DM-Based Onboarding** - Private message onboarding flow with three paths: Apply, Friend/Ally, or Regular User
- 🔄 **Conditional Questions** - Dynamic follow-up questions based on previous answers
- 👥 **Moderation Workflow** - Streamlined review queue for moderators
- 🛡️ **Guild Role Hierarchy** - Sovereign, Templar, Knight, and Squire ranks
- 🎮 **Character Management** - Track game characters (Mortal Online 2 and more)
- 📢 **Bot-Managed Messages** - Welcome and rules messages managed by the bot
- ⚙️ **Fully Configurable** - No hard-coded values, everything stored in database
- 🔒 **Role-Based Permissions** - Hierarchical permission system
- 📊 **Audit Logging** - Track all moderator actions
- 🚀 **PostgreSQL Ready** - SQLite by default, easy migration to PostgreSQL

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Onboarding System](#onboarding-system)
- [Role Hierarchy](#role-hierarchy)
- [Commands](#commands)
- [Conditional Questions](#conditional-questions)
- [Bot-Managed Messages](#bot-managed-messages)
- [Operations Guide](#operations-guide)

## Requirements

- Python 3.9 or higher
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- SQLite (included with Python) or PostgreSQL (optional)

## Installation

### 1. Clone or Download

```bash
git clone <repository-url>
cd discord-onboarding-bot
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

**Required Environment Variables:**

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
DATABASE_URL=sqlite:///bot.db
```

## Configuration

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Go to "Bot" section and click "Add Bot"
4. Under "Privileged Gateway Intents", enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Copy the bot token and add to `.env`
6. Go to "OAuth2 > URL Generator"
7. Select scopes: `bot` and `applications.commands`
8. Select permissions:
   - Manage Roles
   - Ban Members
   - Send Messages
   - Manage Messages (for bot-managed messages)
   - Embed Links
   - Use Slash Commands
9. Copy the generated URL and invite the bot to your server

## Onboarding System

### How It Works

When a member joins your server, they receive a **DM from the bot** with three options:

#### 🛡️ Apply to Join
- Full application process with customizable questions
- Automatically assigned APPLICANT role while pending
- Questions can have conditional follow-ups
- Auto-flagged for immediate reject answers
- Reviewed by moderators in private queue

#### 🤝 Friend/Ally
- For members from other guilds or friend referrals
- Simple text field to explain who they are
- Sent to moderator queue for approval
- Can be assigned any role tier upon approval

#### 👤 Regular User
- No onboarding needed
- Immediate access to server
- No special roles assigned

### Why DM-Based?

- **Privacy**: Applicants don't expose answers publicly
- **Cleaner Server**: No spam in public channels
- **Better UX**: Interactive buttons and forms in a private space
- **Persistent**: Members can complete at their own pace

## Role Hierarchy

The bot implements a guild-based role system:

| Role Tier | Discord Name | Description | Hierarchy Level |
|-----------|--------------|-------------|-----------------|
| **Sovereign** | Guild Leader | Full administrative control | 4 |
| **Templar** | Moderator | Can review applications and moderate | 3 |
| **Knight** | Trusted Member | Special privileged member role | 2 |
| **Squire** | Member | Approved guild member | 1 |
| **Applicant** | Pending | Application submitted, awaiting review | 0 |

### Role Management

- Roles are **stored in the database** per member
- Moderators can `/promote` and `/demote` members
- Role assignments trigger announcements
- Old roles automatically removed on promotion/demotion

### Setup Roles

```
/set_role role_tier:sovereign role:@Guild Leader
/set_role role_tier:templar role:@Moderator
/set_role role_tier:knight role:@Knight
/set_role role_tier:squire role:@Member
/set_role role_tier:applicant role:@Applicant
```

## Commands

### Member Commands

| Command | Description |
|---------|-------------|
| N/A | Onboarding starts automatically via DM on join |
| `/character_add` | Add a new game character |
| `/character_list` | View your characters |
| `/character_remove` | Remove a character |

### Moderator Commands (Templar+)

| Command | Description |
|---------|-------------|
| `/queue` | View pending applications and friend requests |
| `/review <submission_id>` | Review a specific application |
| `/promote <member> <tier>` | Promote member to higher role |
| `/demote <member> <tier>` | Demote member to lower role |

### Admin Commands (Sovereign)

| Command | Description |
|---------|-------------|
| `/admin_help` | View all admin commands |
| `/set_channel` | Configure bot channels |
| `/set_role` | Configure role hierarchy |
| `/add_game` | Add a supported game |
| `/add_question` | Add application question |
| `/add_conditional_question` | Add follow-up question |
| `/set_welcome_message` | Set welcome channel message |
| `/set_rules_message` | Set rules channel message |
| `/update_welcome_message` | Update existing welcome |
| `/update_rules_message` | Update existing rules |
| `/set_welcome` | Set welcome announcement template |
| `/view_config` | View current configuration |
| `/health` | Check bot health status |

## Conditional Questions

Conditional questions appear based on the user's previous answers.

### Example Flow

**Main Question**: "How did you find our server?"
- Option 1: "Friend/Referral"
- Option 2: "Discord Server List"
- Option 3: "Other"

**Conditional Question** (if "Friend/Referral" selected):
"Who referred you? Please provide their username so we can verify."

**Conditional Question** (if "Other" selected):
"Please tell us how you found us:"

### Adding Conditional Questions

1. First add the parent question:
```
/add_question
```

2. Note the question ID from the response

3. Add the conditional question:
```
/add_conditional_question parent_question_id:1 parent_option_text:"Friend/Referral"
```

4. Fill out the modal with the follow-up question details

### Use Cases

- **Referral Verification**: Ask for referrer name when they select "Friend"
- **Detailed Feedback**: Ask "What other game?" if they select "Other games"
- **Policy Acceptance**: Show additional terms if they answer certain ways
- **Custom Paths**: Create different question branches for different types of applicants

## Bot-Managed Messages

The bot can manage welcome and rules messages, ensuring they're:
- Not tied to a specific user account
- Easily updatable by admins
- Consistent in format
- Support media (images/videos via URLs)

### Setup Welcome Message

```
/set_channel channel_type:welcome channel:#welcome
/set_welcome_message
```

Fill in the modal:
- **Message Content**: The text to display
- **Media URL** (optional): Direct link to image/video

### Setup Rules Message

```
/set_channel channel_type:rules channel:#rules
/set_rules_message
```

Fill in the modal:
- **Rules Content**: The server rules
- **Media URL** (optional): Direct link to image/video

### Updating Messages

To update existing messages:
```
/update_welcome_message
/update_rules_message
```

**Note**: To display media inline (not just as a link), manually edit the message in Discord and attach the file directly.

## Channel Configuration

Required channels:

```
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_channel channel_type:welcome channel:#welcome
/set_channel channel_type:rules channel:#rules
```

## Initial Setup

### 1. Start the Bot

```bash
python bot/bot.py
```

### 2. Seed Default Data

```bash
python bot/seed_data.py YOUR_GUILD_ID
```

This creates:
- Default application questions with conditional follow-ups
- Mortal Online 2 game entry
- Default configuration

### 3. Configure Channels

```
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_channel channel_type:welcome channel:#welcome
/set_channel channel_type:rules channel:#rules
```

### 4. Configure Roles

```
/set_role role_tier:sovereign role:@Guild Leader
/set_role role_tier:templar role:@Moderator
/set_role role_tier:knight role:@Knight
/set_role role_tier:squire role:@Member
/set_role role_tier:applicant role:@Applicant
```

### 5. Set Bot-Managed Messages

```
/set_welcome_message
/set_rules_message
```

### 6. Verify Setup

```
/view_config
/health
```

## Operations Guide

### Application Review Workflow

1. Member joins server
2. Bot sends DM with three options
3. Member selects path (Apply/Friend/Regular)
4. **If Apply**: Complete multi-step application in DMs
5. **If Friend**: Provide information about themselves
6. Bot posts to moderator queue
7. Moderator uses `/queue` to see pending
8. Moderator uses `/review <id>` for details
9. Moderator approves with role selection or rejects
10. Member receives DM notification
11. Announcement posted in public channel

### Managing Members

**Promote a Squire to Knight**:
```
/promote member:@Username role_tier:knight
```

**Demote a Knight to Squire**:
```
/demote member:@Username role_tier:squire
```

**Remove all roles**:
```
/demote member:@Username role_tier:none
```

### Customizing Questions

**Add a new question**:
```
/add_question
```

**Add a follow-up based on answer**:
```
/add_conditional_question parent_question_id:5 parent_option_text:"Yes"
```

## Database Schema

### Key Models

- **Guild**: Discord server information
- **Member**: User records with `role_tier` field
- **Submission**: Applications/requests with `submission_type` (applicant/friend/regular)
- **Question**: Application questions with `parent_question_id` and `parent_option_id` for conditionals
- **QuestionOption**: Answer choices with `immediate_reject` flag
- **Answer**: User responses linked to questions
- **RoleRegistry**: Role configuration with hierarchy levels
- **Configuration**: Server settings including bot-managed message IDs

## Troubleshooting

### Members not receiving DMs

**Solution**: Ensure members have DMs enabled. The bot will try to post a fallback message in the welcome channel if DMs fail.

### Conditional questions not appearing

**Solution**: Ensure `parent_option_id` matches exactly with the option the user selected. Check with `/view_config`.

### Roles not being assigned

**Solution**: 
1. Ensure bot's role is **higher** than the roles it's trying to assign
2. Verify roles are configured: `/view_config`
3. Check bot has "Manage Roles" permission

### Bot-managed messages not updating

**Solution**:
1. Ensure bot has "Manage Messages" permission
2. Check the message wasn't deleted
3. Use `/set_welcome_message` again if needed

### Application role not removed after approval

**Solution**: Ensure APPLICANT role is configured and bot can manage it.

## Advanced Configuration

### PostgreSQL Migration

```env
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

### Custom Onboarding Paths

Modify `onboarding.py` to add additional onboarding paths beyond Apply/Friend/Regular.

### Webhook Integration

Connect moderator actions to external webhooks for logging or integration with other tools.

## Security Best Practices

1. **Never commit `.env`** - Contains sensitive tokens
2. **Use strong role hierarchy** - Ensure bot role is positioned correctly
3. **Regular backups** - Backup `bot.db` or PostgreSQL regularly
4. **Monitor logs** - Check `bot.log` for suspicious activity
5. **Limit admin access** - Only trust Sovereign role to server owner

## Support

For issues:
1. Check `bot.log`
2. Use `/health` to verify setup
3. Review this README
4. Check Discord.py documentation

## License

[Add your license information here]

## Credits

Built with:
- [discord.py](https://github.com/Rapptz/discord.py)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- Python 3.9+

---

**Version**: 2.0 with DM Onboarding, Conditional Questions, and Bot-Managed Messages