#!/bin/bash
#
# Setup cron job for Task Scheduler (alternative to systemd)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}Task Scheduler Cron Setup${NC}"
echo "========================="

# Check if project directory exists
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo -e "${RED}Project directory not found: $PROJECT_DIR${NC}"
    exit 1
fi

# Check if main.py exists
if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
    echo -e "${RED}main.py not found in: $PROJECT_DIR${NC}"
    exit 1
fi

# Read Python executable from config
CONFIG_FILE="$PROJECT_DIR/config/config.yaml"
PYTHON_EXECUTABLE="python3"  # Default fallback

if [[ -f "$CONFIG_FILE" ]]; then
    # Extract python_executable from YAML config
    PYTHON_EXECUTABLE=$(grep "python_executable:" "$CONFIG_FILE" | sed 's/.*python_executable: *"\([^"]*\)".*/\1/')
    if [[ -z "$PYTHON_EXECUTABLE" ]]; then
        PYTHON_EXECUTABLE="python3"  # Fallback if not found
    fi
fi

echo -e "${YELLOW}Using Python executable: $PYTHON_EXECUTABLE${NC}"

# Create virtual environment if it doesn't exist
if [[ ! -d "$PROJECT_DIR/venv" ]]; then
    echo -e "${YELLOW}Creating virtual environment with $PYTHON_EXECUTABLE${NC}"
    cd "$PROJECT_DIR"
    "$PYTHON_EXECUTABLE" -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Create wrapper script
WRAPPER_SCRIPT="$PROJECT_DIR/scripts/run_scheduler.sh"
echo -e "${YELLOW}Creating wrapper script: $WRAPPER_SCRIPT${NC}"

cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
# Task Scheduler wrapper script for cron

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run the scheduler
"$PYTHON_EXECUTABLE" main.py --config config/config.yaml

# Log exit code
echo "Task scheduler exited with code: \$?" >> logs/cron.log
EOF

chmod +x "$WRAPPER_SCRIPT"

# Create log rotation script
LOG_ROTATE_SCRIPT="$PROJECT_DIR/scripts/rotate_logs.sh"
echo -e "${YELLOW}Creating log rotation script: $LOG_ROTATE_SCRIPT${NC}"

cat > "$LOG_ROTATE_SCRIPT" << EOF
#!/bin/bash
# Log rotation script for Task Scheduler

LOG_DIR="$PROJECT_DIR/logs"
MAX_SIZE=10485760  # 10MB in bytes

# Rotate logs if they're too large
for log_file in "\$LOG_DIR"/*.log; do
    if [[ -f "\$log_file" && \$(stat -c%s "\$log_file") -gt \$MAX_SIZE ]]; then
        mv "\$log_file" "\${log_file}.old"
        touch "\$log_file"
        echo "Rotated log: \$log_file"
    fi
done
EOF

chmod +x "$LOG_ROTATE_SCRIPT"

# Create monitoring script
MONITOR_SCRIPT="$PROJECT_DIR/scripts/monitor_scheduler.sh"
echo -e "${YELLOW}Creating monitoring script: $MONITOR_SCRIPT${NC}"

cat > "$MONITOR_SCRIPT" << EOF
#!/bin/bash
# Monitor MyAutoHub Task Scheduler and restart if needed
# This script uses the new process naming and restart functionality

# Get script directory and project root
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"
LOGFILE="\$PROJECT_ROOT/logs/monitor.log"
CONFIG_FILE="\$PROJECT_ROOT/config/config.yaml"

# Function to log with timestamp
log_message() {
    echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1" >> "\$LOGFILE"
}

# Function to check if scheduler is running using process name
is_scheduler_running() {
    # Use pgrep to find myautohub-scheduler process
    if pgrep -f "myautohub-scheduler" > /dev/null 2>&1; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

# Function to get scheduler PID
get_scheduler_pid() {
    pgrep -f "myautohub-scheduler" 2>/dev/null | head -1
}

# Create logs directory if it doesn't exist
mkdir -p "\$PROJECT_ROOT/logs"

# Check if scheduler is running
if is_scheduler_running; then
    PID=\$(get_scheduler_pid)
    log_message "Scheduler is running (PID: \$PID)"
    exit 0
fi

# Scheduler is not running, start it
log_message "Scheduler not found, starting Task Scheduler"
cd "\$PROJECT_ROOT"

# Use the restart script to start the scheduler
if [[ -f "\$SCRIPT_DIR/restart_scheduler.py" ]]; then
    # Use our Python restart script for reliable startup
    log_message "Using restart_scheduler.py to start scheduler"
    if "$PYTHON_EXECUTABLE" "\$SCRIPT_DIR/restart_scheduler.py" --timeout 10 >> "\$LOGFILE" 2>&1; then
        PID=\$(get_scheduler_pid)
        if [[ -n "\$PID" ]]; then
            log_message "Successfully started Task Scheduler (PID: \$PID)"
        else
            log_message "ERROR: restart_scheduler.py completed but no scheduler process found"
            exit 1
        fi
    else
        log_message "ERROR: Failed to start scheduler using restart_scheduler.py"
        exit 1
    fi
else
    # Fallback to direct startup if restart script not available
    log_message "restart_scheduler.py not found, using fallback startup method"
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    fi

    # Start scheduler as detached process
    nohup "$PYTHON_EXECUTABLE" main.py --config "\$CONFIG_FILE" > logs/scheduler.out 2>&1 &
    STARTUP_PID=\$!

    # Give it time to start and set process name
    sleep 3

    # Verify it started with correct process name
    PID=\$(get_scheduler_pid)
    if [[ -n "\$PID" ]]; then
        log_message "Successfully started Task Scheduler (PID: \$PID)"
    else
        log_message "ERROR: Failed to start scheduler (startup PID was \$STARTUP_PID)"
        exit 1
    fi
fi

log_message "Monitor script completed successfully"
EOF

chmod +x "$MONITOR_SCRIPT"

# Suggest cron entries
echo -e "${GREEN}Setup completed!${NC}"
echo ""
echo "To set up cron jobs, run the following commands:"
echo ""
echo -e "${YELLOW}1. Edit crontab:${NC}"
echo "   crontab -e"
echo ""
echo -e "${YELLOW}2. Add these entries:${NC}"
echo ""
echo "# Start/monitor Task Scheduler every 5 minutes"
echo "*/5 * * * * $MONITOR_SCRIPT"
echo ""
echo "# Rotate logs daily at 2 AM"
echo "0 2 * * * $LOG_ROTATE_SCRIPT"
echo ""
echo "# Optional: Restart scheduler daily at 3 AM (for memory cleanup)"
echo "0 3 * * * $PYTHON_EXECUTABLE $PROJECT_DIR/scripts/restart_scheduler.py --timeout 10"
echo ""
echo -e "${YELLOW}3. Manual commands:${NC}"
echo "   # Start scheduler:"
echo "   $WRAPPER_SCRIPT"
echo "   # Or use the restart script:"
echo "   $PYTHON_EXECUTABLE $PROJECT_DIR/scripts/restart_scheduler.py"
echo ""
echo -e "${YELLOW}4. Check status:${NC}"
echo "   # Check if scheduler is running:"
echo "   ps aux | grep myautohub-scheduler"
echo "   # Or use the restart script in dry-run mode:"
echo "   $PYTHON_EXECUTABLE $PROJECT_DIR/scripts/restart_scheduler.py --dry-run"
echo "   # View logs:"
echo "   tail -f $PROJECT_DIR/logs/scheduler.log"
echo "   tail -f $PROJECT_DIR/logs/monitor.log"
