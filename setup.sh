#!/bin/bash
# File: setup.sh
# Location: /setup.sh
# Setup script for initial bot installation

set -e

echo "🤖 Discord Onboarding Bot - Setup Script"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.9"

if (( $(echo "$python_version < $required_version" | bc -l) )); then
    echo "❌ Error: Python 3.9 or higher is required (found $python_version)"
    exit 1
fi
echo "✅ Python $python_version detected"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "⚠️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Discord bot token!"
    echo "   Run: nano .env"
else
    echo "⚠️  .env file already exists"
fi
echo ""

# Make scripts executable
chmod +x run.sh
echo "✅ Made run.sh executable"
echo ""

echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your DISCORD_TOKEN"
echo "2. Invite the bot to your Discord server"
echo "3. Run: ./run.sh"
echo "4. In Discord, run: /admin_help"
echo "5. Configure channels and roles"
echo "6. Run seed script: python bot/seed_data.py YOUR_GUILD_ID"
echo ""
echo "For detailed instructions, see README.md"