# File Structure

Complete file structure and description for the Discord Onboarding Bot.

## Project Layout

```
discord-onboarding-bot/
├── bot/                          # Main application directory
│   ├── bot.py                    # Main bot entry point
│   ├── config.py                 # Configuration management
│   ├── database.py               # Database connection and management
│   ├── models.py                 # SQLAlchemy database models
│   ├── seed_data.py              # Database seeding script
│   ├── cogs/                     # Bot command modules (cogs)
│   │   ├── admin.py              # Admin configuration commands
│   │   ├── characters.py         # Character management features
│   │   ├── moderation.py         # Moderation review workflow
│   │   └── onboarding.py         # Application and onboarding system
│   └── utils/                    # Utility modules
│       ├── checks.py             # Permission check decorators
│       └── helpers.py            # Helper functions and utilities
├── .env                          # Environment variables (create from .env.example)
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore file
├── requirements.txt              # Python dependencies
├── setup.sh                      # Setup script (Linux/Mac)
├── run.sh                        # Run script (Linux/Mac)
├── Dockerfile                    # Docker container definition
├── docker-compose.yml            # Docker Compose configuration
├── discord-bot.service           # systemd service file
├── README.md                     # Main documentation
├── QUICKSTART.md                 # Quick start guide
├── DEPLOYMENT.md                 # Deployment guide
└── FILE_STRUCTURE.md             # This file
```

## File Descriptions

### Core Application Files

#### `bot/bot.py`
**Location:** `/bot/bot.py`
**Purpose:** Main entry point for the bot
**Key Features:**
- Bot initialization and configuration
- Event handlers (on_ready, on_guild_join, etc.)
- Cog loading and command syncing
- Error handling
- Graceful shutdown

**Usage:**
```bash
python bot/bot.py
```

#### `bot/config.py`
**Location:** `/bot/config.py`
**Purpose:** Configuration management from environment variables
**Key Features:**
- Loads and validates environment variables
- Provides typed configuration access
- Validates required settings

**Configuration Options:**
- `DISCORD_TOKEN` - Discord bot token (required)
- `DATABASE_URL` - Database connection string
- `LOG_LEVEL` - Logging verbosity
- `DEBUG_MODE` - Debug mode toggle

#### `bot/database.py`
**Location:** `/bot/database.py`
**Purpose:** Database connection and session management
**Key Features:**
- SQLAlchemy engine creation
- Session factory and scoped sessions
- Context manager for transactions
- Table creation and management
- PostgreSQL and SQLite support

**Usage:**
```python
from database import db

with db.session_scope() as session:
    # Your database operations
    pass
```

#### `bot/models.py`
**Location:** `/bot/models.py`
**Purpose:** SQLAlchemy ORM models
**Key Models:**
- `Guild` - Discord server information
- `Member` - User membership and status
- `Submission` - Application submissions
- `Question` - Application questions
- `QuestionOption` - Multiple choice options
- `Answer` - User responses
- `Character` - Game character profiles
- `Game` - Supported games
- `ChannelRegistry` - Channel configuration
- `RoleRegistry` - Role configuration
- `ModeratorAction` - Audit log
- `Configuration` - Server settings

#### `bot/seed_data.py`
**Location:** `/bot/seed_data.py`
**Purpose:** Initialize database with default data
**Features:**
- Creates default application questions
- Sets up default games (Mortal Online 2)
- Initializes configuration
- Validates guild exists before seeding

**Usage:**
```bash
python bot/seed_data.py YOUR_GUILD_ID
```

### Command Modules (Cogs)

#### `bot/cogs/onboarding.py`
**Location:** `/bot/cogs/onboarding.py`
**Purpose:** Member onboarding and application system
**Key Features:**
- Welcome message on member join
- `/apply` command - Start/resume application
- Interactive question flow using modals and selects
- Progress saving and resumption
- Immediate reject flagging
- Submission to moderator queue

**Commands:**
- `/apply` - Start or continue application

**Views/Modals:**
- `QuestionView` - Multiple choice questions
- `QuestionModal` - Text/numeric input
- `ModReviewView` - Moderator review controls
- `RejectModal` - Rejection reason input

#### `bot/cogs/moderation.py`
**Location:** `/bot/cogs/moderation.py`
**Purpose:** Application review and moderation workflow
**Key Features:**
- View pending applications queue
- Detailed application review
- Approve/reject with reason
- Ban option on rejection
- Welcome announcements
- Audit logging

**Commands:**
- `/queue` - View pending applications
- `/review <id>` - Review specific application

**Views/Modals:**
- `ReviewActionView` - Approve/reject buttons
- `RejectDecisionModal` - Rejection details
- `BanConfirmView` - Ban confirmation

#### `bot/cogs/characters.py`
**Location:** `/bot/cogs/characters.py`
**Purpose:** Character and game profile management
**Key Features:**
- Add characters for supported games
- List user's characters
- Remove characters
- Game-specific fields (Mortal Online 2)
- JSON storage for roles/professions

**Commands:**
- `/character` - Character management menu
- `/character_add` - Add new character
- `/character_list` - View characters
- `/character_remove` - Remove character

**Views/Modals:**
- `GameSelectView` - Select game for character
- `CharacterModal` - Character details input
- `CharacterRemoveView` - Select character to remove
- `ConfirmRemoveView` - Confirm deletion

#### `bot/cogs/admin.py`
**Location:** `/bot/cogs/admin.py`
**Purpose:** Bot configuration and administration
**Key Features:**
- Channel configuration
- Role hierarchy setup
- Game management
- Question management
- Welcome message templates
- Configuration viewing
- Health checks

**Commands:**
- `/admin_help` - Admin command list
- `/set_channel` - Configure channels
- `/set_role` - Configure roles
- `/add_game` - Add supported game
- `/add_question` - Add application question
- `/set_welcome` - Set welcome template
- `/view_config` - View configuration
- `/health` - Bot health status

**Views/Modals:**
- `AddQuestionModal` - Question creation form

### Utility Modules

#### `bot/utils/helpers.py`
**Location:** `/bot/utils/helpers.py`
**Purpose:** Reusable helper functions
**Key Functions:**
- `get_or_create_guild()` - Guild record management
- `get_or_create_member()` - Member record management
- `get_channel_id()` - Retrieve configured channels
- `set_channel()` - Configure channels
- `get_role_id()` - Retrieve configured roles
- `set_role()` - Configure roles
- `create_embed()` - Standard embed creation
- `try_send_dm()` - Safe DM sending
- `is_blacklisted()` - Check blacklist status
- `chunk_list()` - List pagination

#### `bot/utils/checks.py`
**Location:** `/bot/utils/checks.py`
**Purpose:** Permission checking decorators
**Key Functions:**
- `has_role_tier()` - Check role hierarchy
- `is_admin()` - Admin check
- `is_moderator()` - Moderator check
- `is_member()` - Member check
- `check_blacklist()` - Blacklist check
- `require_admin()` - Decorator for admin commands
- `require_moderator()` - Decorator for mod commands
- `require_member()` - Decorator for member commands
- `require_not_blacklisted()` - Decorator for blacklist check
- `can_moderate_submission()` - Submission moderation check

### Configuration Files

#### `.env.example`
**Location:** `/.env.example`
**Purpose:** Template for environment variables
**Copy to `.env` and fill in values**

#### `.env`
**Location:** `/.env`
**Purpose:** Actual environment variables
**⚠️ Never commit to git - contains secrets**

#### `requirements.txt`
**Location:** `/requirements.txt`
**Purpose:** Python package dependencies
**Install with:** `pip install -r requirements.txt`

### Deployment Files

#### `setup.sh`
**Location:** `/setup.sh`
**Purpose:** Automated setup script (Linux/Mac)
**Features:**
- Checks Python version
- Creates virtual environment
- Installs dependencies
- Creates .env from template
- Makes scripts executable

**Usage:**
```bash
chmod +x setup.sh
./setup.sh
```

#### `run.sh`
**Location:** `/run.sh`
**Purpose:** Simple bot startup script
**Features:**
- Activates virtual environment
- Runs bot

**Usage:**
```bash
chmod +x run.sh
./run.sh
```

#### `Dockerfile`
**Location:** `/Dockerfile`
**Purpose:** Docker container definition
**Features:**
- Python 3.11 base image
- PostgreSQL client included
- Non-root user
- Health check
- Optimized layer caching

**Build:**
```bash
docker build -t discord-bot .
```

#### `docker-compose.yml`
**Location:** `/docker-compose.yml`
**Purpose:** Docker Compose orchestration
**Features:**
- Bot service configuration
- PostgreSQL service (optional)
- Volume management
- Network isolation

**Usage:**
```bash
docker-compose up -d
```

#### `discord-bot.service`
**Location:** `/discord-bot.service` (copy to `/etc/systemd/system/`)
**Purpose:** systemd service definition
**Features:**
- Auto-restart on failure
- Logging to systemd journal
- Security hardening
- Boot startup

**Install:**
```bash
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

### Documentation Files

#### `README.md`
**Location:** `/README.md`
**Purpose:** Main documentation
**Contents:**
- Feature overview
- Installation instructions
- Configuration guide
- Command reference
- Operations guide
- Troubleshooting

#### `QUICKSTART.md`
**Location:** `/QUICKSTART.md`
**Purpose:** Quick setup guide
**Contents:**
- 10-minute setup
- Step-by-step instructions
- Common issues
- Testing checklist

#### `DEPLOYMENT.md`
**Location:** `/DEPLOYMENT.md`
**Purpose:** Deployment guide
**Contents:**
- Development setup
- Docker deployment
- Linux server deployment
- PostgreSQL setup
- Monitoring and logging
- Backup strategies
- Security best practices

#### `FILE_STRUCTURE.md`
**Location:** `/FILE_STRUCTURE.md`
**Purpose:** This file - complete file reference

### Other Files

#### `.gitignore`
**Location:** `/.gitignore`
**Purpose:** Git ignore patterns
**Ignores:**
- `.env` files
- `__pycache__/`
- `*.db` database files
- `*.log` files
- Virtual environments
- IDE files

## Generated Files (Not in Repository)

These files are created when the bot runs:

### `bot.db`
SQLite database file (if using SQLite)

### `bot.log`
Application log file

### `__pycache__/`
Python bytecode cache directories

### `venv/`
Python virtual environment directory

## Typical Workflow

### Initial Setup
1. Clone/download repository
2. Run `./setup.sh` or manually create venv
3. Copy `.env.example` to `.env`
4. Add Discord token to `.env`
5. Run `python bot/bot.py`
6. Configure in Discord (`/set_channel`, `/set_role`)
7. Run `python bot/seed_data.py GUILD_ID`

### Development
1. Make code changes
2. Test locally with `python bot/bot.py`
3. Commit changes (ensure .env is not committed)
4. Deploy to production

### Deployment
1. Choose deployment method (Docker, systemd, manual)
2. Follow DEPLOYMENT.md for chosen method
3. Monitor logs for errors
4. Use `/health` to verify operation

## File Dependencies

```
bot.py
├── config.py
├── database.py
│   └── models.py
├── cogs/
│   ├── onboarding.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── utils/helpers.py
│   ├── moderation.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── utils/helpers.py
│   │   └── utils/checks.py
│   ├── characters.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── utils/helpers.py
│   └── admin.py
│       ├── database.py
│       ├── models.py
│       └── utils/helpers.py
└── utils/
    ├── checks.py
    │   ├── database.py
    │   ├── models.py
    │   └── helpers.py
    └── helpers.py
        ├── database.py
        └── models.py
```

## Customization Points

To customize the bot for your needs:

1. **Models** (`models.py`) - Add new database fields
2. **Questions** (`seed_data.py`) - Modify default questions
3. **Games** (`seed_data.py`) - Add game-specific fields
4. **Commands** (`cogs/*.py`) - Add new commands
5. **Views** (`cogs/*.py`) - Customize UI components
6. **Config** (`config.py`) - Add new configuration options

## Support Files to Create

You may want to add:

- `LICENSE` - License file
- `CONTRIBUTING.md` - Contribution guidelines
- `CHANGELOG.md` - Version history
- `alembic/` - Database migration scripts
- `tests/` - Unit tests
- `docs/` - Additional documentation

---

For more information, see the main [README.md](README.md).