#!/bin/bash

# Link Paperpile to Notion - Automated Sync Script
# This script runs the paper synchronization with lock file protection

# Set the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Log file for debugging
LOG_FILE="$SCRIPT_DIR/sync.log"
LOCK_FILE="$SCRIPT_DIR/sync.lock"

# Log rotation settings
MAX_LOG_SIZE=10485760  # 10MB in bytes
MAX_LOG_FILES=5        # Keep 5 old log files

# Function to rotate logs if they get too large
rotate_logs() {
    if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rotating log file (size exceeded ${MAX_LOG_SIZE} bytes)" >> "$LOG_FILE"
        
        # Remove oldest log file if it exists
        if [ -f "${LOG_FILE}.${MAX_LOG_FILES}" ]; then
            rm -f "${LOG_FILE}.${MAX_LOG_FILES}"
        fi
        
        # Shift existing log files
        for i in $(seq $((MAX_LOG_FILES-1)) -1 1); do
            if [ -f "${LOG_FILE}.${i}" ]; then
                mv "${LOG_FILE}.${i}" "${LOG_FILE}.$((i+1))"
            fi
        done
        
        # Move current log to .1
        mv "$LOG_FILE" "${LOG_FILE}.1"
        
        # Create new empty log file
        touch "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log rotated, starting new log file" >> "$LOG_FILE"
    fi
}

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to cleanup old log entries (keep last 1000 lines if file is getting large)
cleanup_logs() {
    if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE" 2>/dev/null || echo 0) -gt 2000 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleaning up log file (keeping last 1000 lines)" >> "$LOG_FILE"
        tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log cleanup completed" >> "$LOG_FILE"
    fi
}

# Function to cleanup lock file on exit
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log "Removed lock file"
    fi
}

# Set up trap to cleanup on exit (success, failure, or interruption)
trap cleanup EXIT INT TERM

# Check if another instance is already running
if [ -f "$LOCK_FILE" ]; then
    # Check if the PID in lock file is still running
    if kill -0 $(cat "$LOCK_FILE") 2>/dev/null; then
        log "Another sync process is already running (PID: $(cat "$LOCK_FILE")). Skipping this execution."
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skipped: Another sync in progress"
        exit 0
    else
        log "Found stale lock file, removing it"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file with current PID
echo $$ > "$LOCK_FILE"
log "Created lock file with PID: $$"

# Rotate logs if necessary before starting
rotate_logs

# Record start time for execution time calculation
START_TIME=$(date +%s)
log "Starting paper sync..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    log "ERROR: .env file not found in $SCRIPT_DIR"
    exit 1
fi

# Check if Rye is available and use it
if command -v rye &> /dev/null; then
    log "Using Rye to run the sync..."
    # Run with Rye which automatically uses the correct virtual environment
    # Set QUIET_MODE for cron to reduce log verbosity
    QUIET_MODE=true rye run python main.py >> "$LOG_FILE" 2>&1
else
    log "Rye not found, trying manual virtual environment activation..."
    
    # Check if Rye's virtual environment exists and activate it
    if [ -d ".venv" ]; then
        log "Activating Rye virtual environment..."
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        log "Activating virtual environment..."
        source venv/bin/activate
    else
        log "WARNING: No virtual environment found"
    fi

    # Check if python3 is available
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log "ERROR: Python not found"
        exit 1
    fi

    log "Running sync with $PYTHON_CMD..."
    
    # Run the sync (capture both stdout and stderr)
    # Set QUIET_MODE for cron to reduce log verbosity
    QUIET_MODE=true $PYTHON_CMD main.py >> "$LOG_FILE" 2>&1
fi

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "Sync completed successfully"
else
    log "Sync failed with exit code $EXIT_CODE"
fi

# Calculate and log execution time
END_TIME=$(date +%s)
EXECUTION_TIME=$((END_TIME - START_TIME))
log "Sync finished (execution time: ${EXECUTION_TIME}s)"

# Cleanup logs if they're getting too long
cleanup_logs

echo "" >> "$LOG_FILE"  # Add blank line for readability

# Lock file will be automatically removed by the trap
