# Discord Onboarding & Member Management Bot

A comprehensive Discord bot for automating member onboarding, application review, and character profile management. Built with Python, discord.py, and SQLAlchemy.

## Features

- 🎯 **Multi-Step Application System** - Interactive onboarding with modals, selects, and buttons
- 👥 **Moderation Workflow** - Streamlined review queue for moderators
- 🎮 **Character Management** - Track game characters (Mortal Online 2 and more)
- ⚙️ **Fully Configurable** - No hard-coded values, everything stored in database
- 🔒 **Role-Based Permissions** - Admin, Moderator, Member, and Applicant tiers
- 📊 **Audit Logging** - Track all moderator actions
- 🚀 **PostgreSQL Ready** - SQLite by default, easy migration to PostgreSQL

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Initial Setup](#initial-setup)
- [Commands](#commands)
- [Database Management](#database-management)
- [Operations Guide](#operations-guide)
- [Troubleshooting](#troubleshooting)

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
   - Embed Links
   - Use Slash Commands
9. Copy the generated URL and invite the bot to your server

### Database Configuration

**SQLite (Default):**
```env
DATABASE_URL=sqlite:///bot.db
```

**PostgreSQL (Production):**
```env
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

## Initial Setup

### 1. Start the Bot

```bash
python bot/bot.py
```

The bot will automatically:
- Create database tables
- Register with your Discord server
- Sync slash commands

### 2. Seed Default Data

Open a new terminal (keep the bot running) and run:

```bash
python bot/seed_data.py YOUR_GUILD_ID
```

To find your guild ID:
1. Enable Developer Mode in Discord (User Settings > Advanced)
2. Right-click your server icon
3. Click "Copy Server ID"

This will create:
- Default application questions
- Mortal Online 2 game entry
- Default configuration

### 3. Configure Channels (In Discord)

Use the following commands as an admin:

```
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_channel channel_type:welcome channel:#welcome
```

### 4. Configure Roles (In Discord)

```
/set_role role_tier:admin role:@Admin hierarchy:3
/set_role role_tier:moderator role:@Moderator hierarchy:2
/set_role role_tier:member role:@Member hierarchy:1
/set_role role_tier:applicant role:@Applicant hierarchy:0
```

### 5. Verify Setup

```
/view_config
/health
```

## Commands

### Member Commands

| Command | Description |
|---------|-------------|
| `/apply` | Start or continue application process |
| `/character_add` | Add a new game character |
| `/character_list` | View your characters |
| `/character_remove` | Remove a character |

### Moderator Commands

| Command | Description |
|---------|-------------|
| `/queue` | View pending applications |
| `/review <submission_id>` | Review a specific application |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin_help` | View all admin commands |
| `/set_channel` | Configure bot channels |
| `/set_role` | Configure role hierarchy |
| `/add_game` | Add a supported game |
| `/add_question` | Add application question |
| `/set_welcome` | Set welcome message template |
| `/view_config` | View current configuration |
| `/health` | Check bot health status |

## Database Management

### Backup (SQLite)

```bash
# Create backup
cp bot.db bot_backup_$(date +%Y%m%d).db

# Restore from backup
cp bot_backup_20240101.db bot.db
```

### PostgreSQL Migration

1. Update `.env`:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
```

2. Install PostgreSQL adapter:
```bash
pip install psycopg2-binary
```

3. Restart the bot - tables will be created automatically

### Database Schema Updates

The bot uses SQLAlchemy for schema management. For production, consider using Alembic for migrations:

```bash
# Install Alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

## Operations Guide

### Starting the Bot

**Development:**
```bash
python bot/bot.py
```

**Production (with systemd):**

Create `/etc/systemd/system/discord-bot.service`:

```ini
[Unit]
Description=Discord Onboarding Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/path/to/bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
sudo systemctl status discord-bot
```

### Monitoring Logs

**View logs:**
```bash
tail -f bot.log
```

**View systemd logs:**
```bash
journalctl -u discord-bot -f
```

### Common Maintenance Tasks

**Add new question:**
```
/add_question
```

**Add new game:**
```
/add_game game_name:"Game Name"
```

**Check bot health:**
```
/health
```

**Update welcome message:**
```
/set_welcome template:"Welcome {mention} to our community! 🎉"
```

## Troubleshooting

### Bot won't start

**Check token:**
```bash
# Verify DISCORD_TOKEN in .env
cat .env | grep DISCORD_TOKEN
```

**Check permissions:**
```bash
# Ensure database file is writable
ls -la bot.db
```

**Check logs:**
```bash
tail -n 50 bot.log
```

### Commands not appearing

1. Check bot has `applications.commands` scope
2. Wait a few minutes for Discord to sync
3. Kick and re-invite bot with proper permissions
4. Check logs for sync errors

### Database errors

**SQLite locked:**
- Close all connections to database
- Ensure only one bot instance is running

**Migration needed:**
- Backup database first
- Delete `bot.db` and restart (caution: data loss)
- Or use Alembic for proper migrations

### Permission errors

**Bot can't assign roles:**
- Ensure bot's role is higher than member role in Discord
- Check bot has "Manage Roles" permission

**Bot can't post in channels:**
- Verify bot has "Send Messages" and "Embed Links" in channel

## File Structure

```
discord-onboarding-bot/
├── bot/
│   ├── bot.py                 # Main bot file
│   ├── config.py              # Configuration
│   ├── database.py            # Database manager
│   ├── models.py              # Database models
│   ├── seed_data.py           # Data seeding script
│   ├── cogs/
│   │   ├── admin.py           # Admin commands
│   │   ├── characters.py      # Character management
│   │   ├── moderation.py      # Moderation workflow
│   │   └── onboarding.py      # Application system
│   └── utils/
│       ├── checks.py          # Permission checks
│       └── helpers.py         # Helper functions
├── .env                       # Environment variables (create from .env.example)
├── .env.example               # Environment template
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── bot.db                     # SQLite database (created automatically)
```

## Data Retention & Privacy

The bot stores:
- User IDs and usernames
- Application responses
- Character profiles
- Moderator actions (audit log)

**To remove a user's data:**
1. Locate user in database by user ID
2. Delete associated records (submissions, characters, etc.)
3. Or implement a `/gdpr_delete` admin command as needed

## Contributing

When adding new features:
1. Follow existing code structure
2. Add proper error handling
3. Update documentation
4. Test thoroughly before deployment

## Support

For issues or questions:
1. Check logs first (`bot.log`)
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