#!/bin/bash
# File: run.sh
# Location: /run.sh
# Simple script to run the bot

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source .venv/bin/activate
fi

# Run the bot
python bot/bot.py