# File: Dockerfile
# Location: /Dockerfile
# Docker container for the Discord bot

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot/ ./bot/
COPY .env.example .

# Create directory for database
RUN mkdir -p /data

# Set environment variable for database path
ENV DATABASE_URL=sqlite:////data/bot.db

# Run as non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app /data
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/data/bot.db').execute('SELECT 1')" || exit 1

# Run the bot
CMD ["python", "bot/bot.py"]