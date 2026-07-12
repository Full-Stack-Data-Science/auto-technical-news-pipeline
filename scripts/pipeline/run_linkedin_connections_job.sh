#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$WORK_DIR/src"
VENV_DIR="$SRC_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

LOG_DIR="$SRC_DIR/logs/linkedin/connections_scraping"
LOG_FILE="$LOG_DIR/linkedin-connections-$(date '+%Y-%m-%d_%H-%M-%S').log"

# ===== LOGGING =====
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ===== PARSE OPTIONS =====
NO_UPLOAD=""
for arg in "$@"; do
    case "$arg" in
        --no-upload) NO_UPLOAD="--no-upload" ;;
    esac
done

log "=========================================="
log "LinkedIn connections scraper job started"
log "Working directory: $WORK_DIR"
log "Source directory: $SRC_DIR"
log "Log file: $LOG_FILE"
if [ -n "$NO_UPLOAD" ]; then
    log "No-upload mode: data will be saved locally only"
fi

# ===== PRE-CHECKS =====
cd "$WORK_DIR" || { log "ERROR: Cannot cd to $WORK_DIR"; exit 1; }

# Check for venv, create if doesn't exist, or use system Python
if [ ! -x "$VENV_PYTHON" ] || [ ! -x "$VENV_PIP" ]; then
    log "WARNING: Python venv not found or incomplete at $VENV_DIR"
    log "Attempting to create virtual environment..."
    if python3 -m venv "$VENV_DIR" 2>/dev/null && [ -x "$VENV_PIP" ]; then
        log "Virtual environment created successfully"
    else
        log "WARNING: Failed to create venv or pip not available (python3-venv may not be installed)"
        log "Falling back to system Python for local testing"
        VENV_PYTHON="python3"
        VENV_PIP="pip3"
    fi
fi

if [ ! -f "$SRC_DIR/requirements.txt" ]; then
    log "ERROR: requirements.txt not found at $SRC_DIR/requirements.txt"
    exit 1
fi

# ===== ENV VARS =====
log "Loading environment variables..."
if [ -f "$SRC_DIR/set_env.sh" ]; then
    source "$SRC_DIR/set_env.sh"
else
    log "WARNING: set_env.sh not found"
fi

export PYTHONPATH="$WORK_DIR:$SRC_DIR"

# ===== DEPENDENCIES =====
log "Installing dependencies..."
"$VENV_PIP" install -r "$SRC_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
log "Dependencies installed"

# ===== RUN CONNECTIONS SCRAPER =====
log "Running LinkedIn connections scraper (headless mode)..."
START_TIME=$(date +%s)

log "Forcing headless Chrome via xvfb-run"
export RUNNING_IN_CRON=1
xvfb-run -a "$VENV_PYTHON" "$SRC_DIR/service/linkedin_connections_scraper_execution.py" \
    --data "$WORK_DIR/data/influencer/linkedin_influencer.json" \
    >> "$LOG_FILE" 2>&1

SCRAPER_EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ "$SCRAPER_EXIT_CODE" -eq 0 ]; then
    log "Connections scraper completed successfully"
else
    log "ERROR: Connections scraper failed with exit code $SCRAPER_EXIT_CODE"
    log "Duration: ${DURATION}s"
    exit 1
fi

log "Duration: ${DURATION}s"
log "Job completed successfully"
log "=========================================="

# ===== CLEANUP =====
log "Cleaning up old logs (older than 7 days)..."
find "$LOG_DIR" -name "linkedin-connections-*.log" -mtime +7 -delete
log "Cleanup completed"

exit 0
