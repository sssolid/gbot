# Deployment Guide

Complete guide for deploying the Discord Onboarding Bot in various environments.

## Table of Contents

- [Development](#development)
- [Docker Deployment](#docker-deployment)
- [Linux Server (systemd)](#linux-server-systemd)
- [PostgreSQL Setup](#postgresql-setup)
- [Monitoring & Logs](#monitoring--logs)
- [Backup & Recovery](#backup--recovery)
- [Security Best Practices](#security-best-practices)

---

## Development

Perfect for testing and development on your local machine.

### Setup

```bash
# Run setup script
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your token
```

### Run

```bash
# Activate venv if not already
source venv/bin/activate

# Run bot
python bot/bot.py

# Or use the run script
./run.sh
```

### Stop

```bash
# Press Ctrl+C in terminal
```

---

## Docker Deployment

Recommended for production. Provides isolation, easy updates, and consistent environment.

### Prerequisites

- Docker installed
- Docker Compose installed

### Quick Start

```bash
# 1. Create .env file
cp .env.example .env
nano .env  # Add your DISCORD_TOKEN

# 2. Build and start
docker-compose up -d

# 3. View logs
docker-compose logs -f bot

# 4. Check status
docker-compose ps
```

### Common Commands

```bash
# Start bot
docker-compose up -d

# Stop bot
docker-compose down

# Restart bot
docker-compose restart

# View logs (follow)
docker-compose logs -f bot

# View last 100 lines
docker-compose logs --tail=100 bot

# Update bot (after code changes)
docker-compose build
docker-compose up -d

# Run seed script
docker-compose exec bot python bot/seed_data.py YOUR_GUILD_ID

# Access Python shell
docker-compose exec bot python
```

### Data Persistence

Data is stored in Docker volumes:

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect discord-onboarding-bot_bot-data

# Backup volume
docker run --rm \
  -v discord-onboarding-bot_bot-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/bot-backup.tar.gz /data
```

### Using PostgreSQL with Docker

Edit `docker-compose.yml` and uncomment the PostgreSQL section:

```yaml
services:
  bot:
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql://botuser:botpass@postgres:5432/botdb

  postgres:
    image: postgres:15-alpine
    # ... (uncomment full section)
```

Then:

```bash
docker-compose down
docker-compose up -d
```

---

## Linux Server (systemd)

For VPS or dedicated server deployment.

### Prerequisites

- Linux server (Ubuntu 20.04+, Debian 11+, etc.)
- Python 3.9+ installed
- sudo access

### Installation

```bash
# 1. Create bot user
sudo useradd -m -s /bin/bash botuser

# 2. Switch to bot user
sudo su - botuser

# 3. Clone/upload bot files
cd /home/botuser
# ... upload your bot files here

# 4. Run setup
./setup.sh

# 5. Configure .env
nano .env

# 6. Test run
./run.sh
# If works, press Ctrl+C
```

### systemd Service Setup

```bash
# Exit bot user
exit

# Copy service file
sudo cp discord-bot.service /etc/systemd/system/

# Edit paths in service file
sudo nano /etc/systemd/system/discord-bot.service
# Update User, Group, WorkingDirectory paths

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable discord-bot

# Start service
sudo systemctl start discord-bot

# Check status
sudo systemctl status discord-bot
```

### Service Management

```bash
# Start
sudo systemctl start discord-bot

# Stop
sudo systemctl stop discord-bot

# Restart
sudo systemctl restart discord-bot

# Status
sudo systemctl status discord-bot

# View logs
sudo journalctl -u discord-bot -f

# View last 100 lines
sudo journalctl -u discord-bot -n 100
```

### Updates

```bash
# 1. Stop service
sudo systemctl stop discord-bot

# 2. Switch to bot user
sudo su - botuser

# 3. Update code
cd /home/botuser/discord-onboarding-bot
git pull  # or upload new files

# 4. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 5. Exit bot user
exit

# 6. Start service
sudo systemctl start discord-bot

# 7. Check status
sudo systemctl status discord-bot
```

---

## PostgreSQL Setup

For production environments requiring better performance and concurrent access.

### Local PostgreSQL

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE botdb;
CREATE USER botuser WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE botdb TO botuser;
\q
```

```bash
# Update .env
DATABASE_URL=postgresql://botuser:your_secure_password@localhost:5432/botdb

# Restart bot
sudo systemctl restart discord-bot
```

### Remote PostgreSQL

```bash
# Update .env with remote host
DATABASE_URL=postgresql://user:pass@remote.host:5432/dbname

# Test connection
psql postgresql://user:pass@remote.host:5432/dbname -c "SELECT 1"
```

### Managed PostgreSQL (AWS RDS, DigitalOcean, etc.)

```bash
# Get connection string from provider
# Usually looks like: postgresql://user:pass@host.region.provider.com:5432/dbname

# Update .env
DATABASE_URL=postgresql://user:pass@host.region.provider.com:5432/dbname
```

---

## Monitoring & Logs

### View Logs

**Development:**
```bash
tail -f bot.log
```

**systemd:**
```bash
sudo journalctl -u discord-bot -f
```

**Docker:**
```bash
docker-compose logs -f bot
```

### Log Rotation

Create `/etc/logrotate.d/discord-bot`:

```
/home/botuser/discord-onboarding-bot/bot.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 botuser botuser
    sharedscripts
    postrotate
        systemctl reload discord-bot > /dev/null 2>&1 || true
    endscript
}
```

### Health Monitoring

**Discord command:**
```
/health
```

**systemd check:**
```bash
sudo systemctl status discord-bot
```

**Docker check:**
```bash
docker-compose ps
docker inspect discord-onboarding-bot | grep Status
```

**Simple monitoring script:**

```bash
#!/bin/bash
# check-bot.sh

if ! sudo systemctl is-active --quiet discord-bot; then
    echo "Bot is down! Restarting..."
    sudo systemctl restart discord-bot
    # Send alert email/webhook here
fi
```

Add to crontab:
```bash
# Check every 5 minutes
*/5 * * * * /path/to/check-bot.sh
```

---

## Backup & Recovery

### SQLite Backup

**Manual:**
```bash
# Backup
cp bot.db bot_backup_$(date +%Y%m%d_%H%M%S).db

# Restore
cp bot_backup_20240101_120000.db bot.db
sudo systemctl restart discord-bot
```

**Automated (cron):**
```bash
#!/bin/bash
# backup-bot.sh

BACKUP_DIR="/home/botuser/backups"
DB_FILE="/home/botuser/discord-onboarding-bot/bot.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
cp "$DB_FILE" "$BACKUP_DIR/bot_backup_$TIMESTAMP.db"

# Keep only last 30 days
find "$BACKUP_DIR" -name "bot_backup_*.db" -mtime +30 -delete
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /home/botuser/backup-bot.sh
```

### PostgreSQL Backup

**Manual:**
```bash
# Backup
pg_dump -h localhost -U botuser botdb > bot_backup_$(date +%Y%m%d).sql

# Restore
psql -h localhost -U botuser botdb < bot_backup_20240101.sql
```

**Automated:**
```bash
#!/bin/bash
# backup-postgres.sh

BACKUP_DIR="/home/botuser/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

pg_dump -h localhost -U botuser botdb | gzip > "$BACKUP_DIR/bot_backup_$TIMESTAMP.sql.gz"

# Keep only last 30 days
find "$BACKUP_DIR" -name "bot_backup_*.sql.gz" -mtime +30 -delete
```

### Docker Volume Backup

```bash
# Backup
docker run --rm \
  -v discord-onboarding-bot_bot-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/bot-backup-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm \
  -v discord-onboarding-bot_bot-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd / && tar xzf /backup/bot-backup-20240101.tar.gz"
```

---

## Security Best Practices

### 1. Environment Variables

```bash
# Never commit .env to git
# Use strong, unique passwords
# Rotate tokens periodically

# Secure .env file permissions
chmod 600 .env
```

### 2. Database Security

```bash
# Restrict database file access
chmod 640 bot.db
chown botuser:botuser bot.db

# For PostgreSQL, use strong passwords
# Enable SSL for remote connections
# Restrict network access
```

### 3. Bot Permissions

- Only grant necessary Discord permissions
- Use least privilege principle
- Regular permission audits

### 4. Server Security

```bash
# Keep system updated
sudo apt update && sudo apt upgrade

# Enable firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 443  # If hosting web interface

# Disable root SSH
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart sshd
```

### 5. Monitoring

```bash
# Monitor for failed login attempts
# Set up alerts for bot downtime
# Review logs regularly
# Monitor resource usage
```

### 6. Backup Encryption

```bash
# Encrypt backups
gpg --encrypt --recipient your@email.com bot_backup.db

# Decrypt
gpg --decrypt bot_backup.db.gpg > bot_backup.db
```

---

## Troubleshooting Deployment

### Bot won't start

```bash
# Check logs
sudo journalctl -u discord-bot -n 50

# Check service status
sudo systemctl status discord-bot

# Test manually
sudo su - botuser
cd discord-onboarding-bot
source venv/bin/activate
python bot/bot.py
```

### Permission errors

```bash
# Check file ownership
ls -la /home/botuser/discord-onboarding-bot

# Fix ownership
sudo chown -R botuser:botuser /home/botuser/discord-onboarding-bot

# Check file permissions
chmod 755 /home/botuser/discord-onboarding-bot
chmod 644 /home/botuser/discord-onboarding-bot/.env
```

### Database locked

```bash
# Check for multiple instances
ps aux | grep "bot.py"

# Kill duplicates
sudo systemctl stop discord-bot
pkill -f "bot.py"
sudo systemctl start discord-bot
```

### Out of memory

```bash
# Check memory usage
free -h
docker stats  # For Docker

# Restart service
sudo systemctl restart discord-bot

# Consider upgrading server or optimizing queries
```

---

## Scaling Considerations

### Multiple Guilds

The bot is designed for multiple guilds out of the box. Each guild has isolated:
- Configuration
- Questions
- Members
- Applications

### High Volume

For high-traffic servers:

1. **Use PostgreSQL** instead of SQLite
2. **Enable connection pooling** in database.py
3. **Monitor performance** regularly
4. **Scale vertically** (more CPU/RAM)
5. **Consider caching** for frequently accessed data

### Horizontal Scaling

For multiple bot instances (advanced):
- Use shared PostgreSQL database
- Implement distributed locking
- Consider message queue for processing
- Load balance across instances

---

For questions or issues, refer to the main [README.md](README.md) or check the logs.