#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
WORK_DIR="$HOME/src"
VENV_DIR="$WORK_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

LOG_DIR="$WORK_DIR/logs/twitter/post_scraping"
LOG_FILE="$LOG_DIR/twitter-scraper-$(date '+%Y-%m-%d_%H-%M-%S').log"

# ===== LOGGING =====
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Twitter scraper job started"
log "Working directory: $WORK_DIR"
log "Log file: $LOG_FILE"

# ===== PRE-CHECKS =====
cd "$WORK_DIR" || { log "ERROR: Cannot cd to $WORK_DIR"; exit 1; }

if [ ! -x "$VENV_PYTHON" ]; then
    log "ERROR: Python venv not found at $VENV_PYTHON"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    log "ERROR: requirements.txt not found"
    exit 1
fi

# ===== ENV VARS =====
log "Loading environment variables..."
if [ -f "$WORK_DIR/set_env.sh" ]; then
    source "$WORK_DIR/set_env.sh"
else
    log "WARNING: set_env.sh not found"
fi

export PYTHONPATH="$WORK_DIR"

# ===== DEPENDENCIES =====
log "Installing dependencies..."
"$VENV_PIP" install -r requirements.txt >> "$LOG_FILE" 2>&1
log "Dependencies installed"

# ===== RUN SCRAPER =====
log "Running Twitter scraper..."
START_TIME=$(date +%s)

xvfb-run -a "$VENV_PYTHON" "$WORK_DIR/service/twitter_scraper_execution.py" \
    >> "$LOG_FILE" 2>&1

SCRAPER_EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ "$SCRAPER_EXIT_CODE" -eq 0 ]; then
    log "Scraper completed successfully"
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
find "$LOG_DIR" -name "twitter-scraper-*.log" -mtime +7 -delete
log "Cleanup completed"

exit 0
