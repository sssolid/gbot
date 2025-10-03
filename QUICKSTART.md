# Quick Start Guide

Get your Discord Onboarding Bot running in 10 minutes!

## Prerequisites

- Python 3.9+ installed
- A Discord account with server admin permissions
- 10 minutes of your time

## Step 1: Get Your Bot Token (3 minutes)

1. Go to https://discord.com/developers/applications
2. Click **"New Application"**
3. Give it a name (e.g., "Onboarding Bot")
4. Go to **"Bot"** section → Click **"Add Bot"**
5. Under **"Privileged Gateway Intents"**, enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
6. Click **"Reset Token"** → **"Copy"** (save this!)

## Step 2: Invite Bot to Server (1 minute)

1. Still in Developer Portal, go to **"OAuth2"** → **"URL Generator"**
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select permissions:
   - ✅ Manage Roles
   - ✅ Ban Members
   - ✅ Send Messages
   - ✅ Embed Links
4. Copy the generated URL at the bottom
5. Open it in your browser and invite bot to your server

## Step 3: Install Bot (2 minutes)

### Linux/Mac:
```bash
# Run setup script
chmod +x setup.sh
./setup.sh

# Edit .env file
nano .env
# Paste your bot token after DISCORD_TOKEN=
# Save: Ctrl+X, Y, Enter
```

### Windows:
```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env
copy .env.example .env

# Edit .env in Notepad
notepad .env
# Add your bot token
```

## Step 4: Start the Bot (1 minute)

```bash
# Linux/Mac
./run.sh

# Windows
python bot/bot.py
```

You should see:
```
Bot is ready! Logged in as YourBot#1234
Connected to 1 guild(s)
```

## Step 5: Configure in Discord (3 minutes)

### Find Your Server ID:
1. Enable Developer Mode: Discord Settings → Advanced → Developer Mode ✅
2. Right-click your server icon → **"Copy Server ID"**

### Create Channels:
Create these channels in Discord:
- `#announcements` (or use existing)
- `#mod-queue` (private for moderators)
- `#welcome` (optional)

### Run Setup Commands:

In Discord, type these commands:

```
/set_channel channel_type:announcements channel:#announcements
/set_channel channel_type:moderator_queue channel:#mod-queue
/set_role role_tier:admin role:@Admin hierarchy:3
/set_role role_tier:moderator role:@Moderator hierarchy:2
/set_role role_tier:member role:@Member hierarchy:1
/view_config
```

### Seed Default Questions:

Back in your terminal (keep bot running in other window):

```bash
# Linux/Mac
source venv/bin/activate
python bot/seed_data.py YOUR_SERVER_ID

# Windows
venv\Scripts\activate
python bot/seed_data.py YOUR_SERVER_ID
```

## Step 6: Test! ✅

1. In Discord, type `/apply`
2. Fill out the application
3. Check `#mod-queue` for the submission
4. Click **Approve** or **Reject**
5. New member should get role and announcement should post!

## What's Next?

### Customize Questions
```
/add_question
```

### Add Games
```
/add_game game_name:"Mortal Online 2"
```

### Customize Welcome Message
```
/set_welcome template:"Welcome {mention} to our awesome community! 🎉"
```

### View All Commands
```
/admin_help
```

## Common Issues

### "Commands not showing up"
- Wait 5 minutes for Discord to sync
- Restart Discord app
- Re-invite bot with correct permissions

### "Permission denied"
- Make sure your role is above the bot's role
- Check bot has proper permissions on server

### "Bot not responding"
- Check bot is online (terminal shows "Bot is ready!")
- Check `.env` has correct token
- Check logs: `tail -f bot.log`

### "Can't approve members"
- Bot's role must be ABOVE the member role in server settings
- Drag bot role higher in Settings → Roles

## Need Help?

1. Check `bot.log` file
2. Run `/health` in Discord
3. See full README.md for detailed docs
4. Make sure all setup steps were completed

## Success Checklist

- ✅ Bot shows as online in Discord
- ✅ `/admin_help` works
- ✅ `/view_config` shows your channels and roles
- ✅ `/apply` shows application form
- ✅ Applications appear in mod queue
- ✅ Approvals assign role and post announcement

**Congratulations! Your bot is ready! 🎉**

---

For advanced configuration, troubleshooting, and production deployment, see the full [README.md](README.md).