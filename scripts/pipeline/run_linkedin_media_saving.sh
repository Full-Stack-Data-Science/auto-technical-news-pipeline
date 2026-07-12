#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Use this script's directory (src) as the working dir so requirements.txt is found
WORK_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN="${PIP_BIN:-pip3}"

LOG_DIR="$WORK_DIR/logs/linkedin/post_media"
LOG_FILE="$LOG_DIR/linkedin-media-$(date '+%Y-%m-%d_%H-%M-%S').log"

# Default parameters (can be overridden by CLI flags)
DAYS_BACK="${DAYS_BACK:-7}"
MAX_IMAGES="${MAX_IMAGES:-}"
ACTIVITY_URL="${ACTIVITY_URL:-}"

# ===== LOGGING =====
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "LinkedIn media saving job started"
log "Working directory: $WORK_DIR"
log "Log file: $LOG_FILE"

# ===== ARG PARSING =====
usage() {
    cat <<EOF
Usage: $(basename "$0") [--days-back N] [--max-images N] [--activity-url URL]

  --days-back N     Number of days to look back for parquet files (default: $DAYS_BACK)
  --max-images N    Maximum number of images to process (default: all)
  --activity-url U  Only process media for this LinkedIn post URL (exact match on post_url)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days-back)
            DAYS_BACK="$2"
            shift 2
            ;;
        --max-images)
            MAX_IMAGES="$2"
            shift 2
            ;;
        --activity-url)
            ACTIVITY_URL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

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

# Storage account creds are required for media saving
if [ -z "${STORAGE_ACCOUNT_NAME:-}" ] || [ -z "${STORAGE_ACCOUNT_KEY:-}" ] || [ -z "${FILE_SYSTEM_NAME:-}" ]; then
    log "ERROR: STORAGE_ACCOUNT_NAME / STORAGE_ACCOUNT_KEY / FILE_SYSTEM_NAME not set. Add them to .env before running media saving job."
    exit 1
fi

# ===== RUN JOB =====
log "Running LinkedIn media saving..."
log "Parameters: days_back=$DAYS_BACK, max_images=${MAX_IMAGES:-all}, activity_url=${ACTIVITY_URL:-<none>}"
START_TIME=$(date +%s)

CMD=( "$PYTHON_BIN" "$WORK_DIR/service/linkedin_media_saving_execution.py"
      --days-back "$DAYS_BACK"
)

if [ -n "$MAX_IMAGES" ]; then
    CMD+=( --max-images "$MAX_IMAGES" )
fi

if [ -n "$ACTIVITY_URL" ]; then
    CMD+=( --activity-url "$ACTIVITY_URL" )
fi

"${CMD[@]}" >> "$LOG_FILE" 2>&1
JOB_EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ "$JOB_EXIT_CODE" -eq 0 ]; then
    log "Media saving completed successfully"
else
    log "ERROR: Media saving job failed with exit code $JOB_EXIT_CODE"
    log "Duration: ${DURATION}s"
    exit 1
fi

log "Duration: ${DURATION}s"
log "Job completed successfully"
log "=========================================="

# ===== CLEANUP =====
log "Cleaning up old logs (older than 7 days)..."
find "$LOG_DIR" -name "linkedin-media-*.log" -mtime +7 -delete
log "Cleanup completed"

exit 0

