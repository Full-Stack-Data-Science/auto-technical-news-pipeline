#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Use this script's directory (src) as the working dir so requirements.txt is found
WORK_DIR="$(cd "$(dirname "$0")" && pwd)"

# Use system Python by default; allow override via PYTHON_BIN / PIP_BIN
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN="${PIP_BIN:-pip3}"

LOG_DIR="$WORK_DIR/logs/twitter/post_publish"
LOG_FILE="$LOG_DIR/twitter-publisher-$(date '+%Y-%m-%d_%H-%M-%S').log"

# ===== LOGGING =====
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Hot trending post publishing job started"
log "Working directory: $WORK_DIR"
log "Log file: $LOG_FILE"

# ===== PRE-CHECKS =====
cd "$WORK_DIR" || { log "ERROR: Cannot cd to $WORK_DIR"; exit 1; }

if [ ! -f "requirements.txt" ]; then
    log "ERROR: requirements.txt not found"
    exit 1
fi

# ===== SETUP VIRTUAL ENVIRONMENT =====
VENV_DIR="$WORK_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV_DIR" || {
        log "ERROR: Failed to create virtual environment. Make sure python3-venv is installed: sudo apt install python3-venv"
        exit 1
    }
    log "Virtual environment created"
fi

# Activate virtual environment
log "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Update PYTHON_BIN and PIP_BIN to use venv
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

# Verify venv is being used
log "Using Python from venv: $PYTHON_BIN"
log "Using pip from venv: $PIP_BIN"

# Install/update dependencies in venv
log "Installing dependencies in virtual environment..."
"$PIP_BIN" install --upgrade pip >/dev/null 2>&1 || true
"$PIP_BIN" install -r requirements.txt || {
    log "ERROR: Failed to install dependencies"
    exit 1
}
log "Dependencies installed successfully in venv"

# ===== ENV VARS =====
log "Loading environment variables..."
if [ -f "$WORK_DIR/set_env.sh" ]; then
    source "$WORK_DIR/set_env.sh"
else
    log "WARNING: set_env.sh not found"
fi

# Load .env file if it exists
if [ -f "$WORK_DIR/.env" ]; then
    log "Loading .env file..."
    # Export variables from .env file (skip comments and empty lines)
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        # Export the variable
        export "$line" 2>/dev/null || true
    done < "$WORK_DIR/.env"
fi

export PYTHONPATH="$WORK_DIR"

# FSDS creds are required to publish
if [ -z "${FSDS_USERNAME:-}" ] || [ -z "${FSDS_PASSWORD:-}" ]; then
    log "ERROR: FSDS_USERNAME / FSDS_PASSWORD not set. Add them to set_env.sh or .env before running publisher."
    exit 1
fi

# ===== RUN JOBS =====
log "Running Twitter post publishing..."
START_TIME=$(date +%s)

xvfb-run -a "$PYTHON_BIN" "$WORK_DIR/service/twitter_trending_posts_publish.py" \
    >> "$LOG_FILE" 2>&1

SCRAPER_EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ "$SCRAPER_EXIT_CODE" -eq 0 ]; then
    log "Pushlish completed successfully"
else
    log "ERROR: Scraper failed with exit code $SCRAPER_EXIT_CODE"
    log "Duration: ${DURATION}s"
    exit 1
fi

log "Duration: ${DURATION}s"
log "Job completed successfully"
log "=========================================="

# ===== CLEANUP =====
log "Cleaning up old logs (older than 7 days)..."
find "$LOG_DIR" -name "twitter-publisher-*.log" -mtime +7 -delete
log "Cleanup completed"

exit 0
