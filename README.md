# Discord Guild Management Bot

A comprehensive Discord bot for gaming guild management with a UI-first approach, database-backed configuration, and admin-approval workflows.

## 🌟 Features

### 🎛️ UI-First Design
- **No command memorization required** - Everything accessible through buttons, dropdowns, and menus
- **Persistent control panels** - Admin Dashboard and Member Hub with always-active controls
- **Context menus** - Right-click actions for quick moderation and management
- **Modal forms** - Intuitive forms for data entry

### 📋 Onboarding System
- **Custom questions** - Create text or single-select questions for new members
- **Rule-based suggestions** - Automatically suggest roles based on answers
- **Admin approval required** - No automatic role assignment, admins review all applications
- **Resume capability** - Members can continue incomplete onboarding sessions

### 👤 Character Profiles
- **Multiple characters per user** - Support for gaming alts and different characters
- **Main character designation** - Set one character as primary
- **Archetype and build notes** - Store character class and build information
- **Admin management** - Admins can view and manage all user profiles

### 📊 Polls & Voting
- **Rich poll creation** - Up to 10 options with visual vote bars
- **Anonymous voting** - Option for anonymous or public votes
- **Scheduling** - Set poll duration with automatic closing
- **Real-time results** - Live vote count updates

### 📢 Announcements
- **Rich formatting** - Embed-based announcements with author attribution
- **Scheduling** - Schedule announcements for future posting
- **Channel targeting** - Send to specific channels
- **@everyone support** - Optional mass mentions

### 🛡️ Auto-Moderation
- **Spam detection** - Configurable message and mention limits
- **Swear filtering** - Custom word lists with wildcard support
- **Channel-specific** - Only moderate selected channels
- **Staff exemptions** - Exclude moderator roles from filtering
- **Incident logging** - Complete audit trail of all moderation actions

### ⚙️ Configuration Management
- **Live configuration** - All settings stored in database, no restarts required
- **UI-based setup** - Configure everything through Discord interfaces
- **Guild-specific** - Separate settings per Discord server
- **Export/import ready** - Database-backed for easy backup and migration

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or higher
- Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- PostgreSQL database (optional, SQLite used by default)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd discord-guild-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your Discord bot token
```

4. **Run the bot**
```bash
python main.py
```

### Initial Setup

1. **Invite the bot to your server** with the following permissions:
   - Manage Roles
   - Manage Channels
   - Send Messages
   - Embed Links
   - Read Message History
   - Moderate Members

2. **Run the setup wizard**
   ```
   /setup
   ```

3. **Deploy control panels**
   - Use the setup wizard to deploy Admin Dashboard and Member Hub
   - Admin Dashboard goes in a staff-only channel
   - Member Hub goes in a public channel (welcome/general)

4. **Configure onboarding** (optional)
   - Add questions through the Admin Dashboard
   - Set up role suggestion rules
   - Test the onboarding flow

## 📖 Usage Guide

### For Administrators

#### Admin Dashboard
Access all administrative functions through the persistent Admin Dashboard:

- **Onboarding Queue** - Review and approve new member applications
- **Announcements** - Create server announcements with scheduling
- **Promotions & Roles** - Manage member roles and promotions
- **Poll Builder** - Create polls for community engagement
- **Moderation Center** - Configure spam/swear filters and view incidents
- **Profiles Admin** - Manage member character profiles
- **Configuration** - Access all bot settings and deployment tools

#### Key Commands
- `/setup` - Initial configuration wizard
- `/config` - Access specific configuration sections
- `/deploy_panels` - Deploy control panels
- `/info` - View bot status and configuration

#### Context Menus (Right-click)
- **Messages**: Moderate message, Create poll from message
- **Users**: Manage roles, View profile

### For Members

#### Member Hub
Access member features through the persistent Member Hub:

- **Start Onboarding** - Complete the server onboarding process
- **My Characters** - Manage your character profiles
- **Create Poll** - Create polls (if permitted by role)
- **Report Message** - Report inappropriate content
- **Server Info & Rules** - View server information

#### Character Management
- Create multiple characters with names, archetypes, and build notes
- Set one character as your "main"
- View other members' profiles

#### Polls & Voting
- Vote on community polls
- View real-time results
- Create polls if you have permission

### For Moderators

#### Moderation Tools
- Access through Admin Dashboard > Moderation Center
- Configure spam and swear filters
- Set watched channels and staff exemptions
- View recent incidents and take action

#### Quick Actions
- `/warn @user reason` - Warn a user
- `/timeout @user duration reason` - Timeout a user
- Context menu moderation on messages and users

## 🗄️ Database Schema

The bot uses SQLAlchemy 2.x with async support. Key tables:

### Core Configuration
- `guild_configs` - Basic guild settings (channels, roles)
- `config_kv` - Key-value configuration storage
- `users` - Guild member records
- `characters` - Member character profiles

### Onboarding System
- `onboarding_questions` - Custom onboarding questions
- `onboarding_rules` - Role suggestion rules
- `onboarding_sessions` - Member onboarding progress

### Features
- `polls` / `poll_votes` - Poll system
- `announcements` - Announcement history
- `moderation_incidents` - Moderation audit log

### Database Migration
The bot automatically creates tables on first run. For production deployments:

1. **SQLite** (default): `sqlite:///guild_bot.sqlite`
2. **PostgreSQL**: `postgresql+asyncpg://user:pass@host/db`

## 🔧 Configuration

### Environment Variables
See `.env.example` for all available options:

- `DISCORD_TOKEN` - Bot token (required)
- `DATABASE_URL` - Database connection string
- `LOG_LEVEL` - Logging verbosity

### Guild Settings
All guild-specific settings are managed through the Discord UI:

1. **Basic Settings** - Channels, default roles
2. **Onboarding** - Questions, rules, approval workflow
3. **Moderation** - Spam/swear filters, watched channels
4. **Polls** - Default settings, creator permissions
5. **Panels** - Control panel deployment

## 📁 Project Structure

```
discord-guild-bot/
├── main.py                 # Bot entry point
├── bot.py                  # Main bot class
├── database.py             # Database models and setup
├── context_menus.py        # Right-click commands
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── README.md              # This file
│
├── utils/
│   ├── permissions.py     # Permission checking utilities
│   └── cache.py          # Configuration caching
│
├── views/
│   ├── panels.py         # Main control panels
│   ├── onboarding.py     # Onboarding UI components
│   ├── profiles.py       # Character profile management
│   ├── polls.py          # Poll creation and voting
│   ├── moderation.py     # Moderation interfaces
│   ├── announcements.py  # Announcement system
│   └── configuration.py  # Settings management
│
└── cogs/
    ├── onboarding.py     # Onboarding commands
    ├── profiles.py       # Profile commands
    ├── polls.py          # Poll commands
    ├── moderation.py     # Moderation commands
    ├── announcements.py  # Announcement commands
    └── configuration.py  # Configuration commands
```

## 🔒 Security & Permissions

### Bot Permissions
The bot requires specific Discord permissions to function:

**Essential Permissions:**
- Manage Roles (for role assignment)
- Send Messages (for all communications)
- Embed Links (for rich formatting)
- Read Message History (for moderation)

**Optional Permissions:**
- Manage Messages (for message deletion in moderation)
- Moderate Members (for timeouts)
- Manage Channels (for advanced features)

### Access Control
- **Admin functions** require Administrator, Manage Server, or Manage Roles
- **Moderator functions** require the above plus Manage Messages or Moderate Members
- **Member functions** are available to all non-bot users
- **Role assignment** always requires explicit admin approval

### Data Privacy
- All data is stored locally in your database
- No data is transmitted to external services
- Member data includes only Discord IDs and user-provided character information
- Moderation logs include message snapshots for context

## 🤝 Contributing

### Development Setup
1. Clone the repository
2. Install dependencies with `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure
4. Run `python main.py`

### Code Style
- Use `black` for code formatting
- Follow PEP 8 guidelines
- Add type hints where possible
- Document complex functions

### Testing
- Test all UI components thoroughly
- Verify database migrations work correctly
- Ensure proper permission checking
- Test edge cases and error handling

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

**Bot not responding to interactions:**
- Check bot permissions in the channel
- Verify the bot token is correct
- Ensure the bot is online and connected

**Database errors:**
- Check database connection string
- Ensure database server is running (for PostgreSQL)
- Verify file permissions (for SQLite)

**Permissions errors:**
- Check bot role hierarchy (bot role must be above managed roles)
- Verify required permissions are granted
- Check channel-specific permission overrides

### Getting Help

1. Check the [Issues](issues) page for known problems
2. Review the configuration settings in `/config`
3. Check bot logs for error messages
4. Ensure all dependencies are installed correctly

### Reporting Bugs

When reporting issues, please include:
- Discord.py version and Python version
- Database type (SQLite/PostgreSQL)
- Error messages from logs
- Steps to reproduce the issue
- Bot configuration (without sensitive data)

## 🏗️ Architecture Notes

### Design Principles

1. **UI-First**: All features accessible through Discord's UI components
2. **Database-Driven**: Configuration stored in database, not files
3. **Admin-Controlled**: No automatic role assignment, admin approval required
4. **Persistent Views**: Control panels survive bot restarts
5. **Permission-Aware**: Proper access control at every level

### Key Technologies

- **discord.py 2.x**: Modern Discord API wrapper with app commands
- **SQLAlchemy 2.x**: Async ORM for database operations
- **Pydantic**: Data validation and settings management
- **aiosqlite/asyncpg**: Async database drivers

### Performance Considerations

- Configuration caching to reduce database queries
- Efficient pagination for large datasets
- Minimal memory footprint for persistent views
- Optimized database queries with proper indexing

This bot is designed to be production-ready while remaining easy to deploy and maintain. The UI-first approach ensures a smooth experience for both administrators and members, while the database-backed configuration provides flexibility and reliability.