#!/bin/bash
"""
Installation script for Task Scheduler
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/task-scheduler"
SERVICE_NAME="task-scheduler"
USER="task-scheduler"

echo -e "${GREEN}Task Scheduler Installation Script${NC}"
echo "=================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Create user if it doesn't exist
if ! id "$USER" &>/dev/null; then
    echo -e "${YELLOW}Creating user: $USER${NC}"
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER"
fi

# Create installation directory
echo -e "${YELLOW}Creating installation directory: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"
chown -R "$USER:$USER" "$INSTALL_DIR"

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies${NC}"
cd "$INSTALL_DIR"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Make scripts executable
chmod +x main.py
chmod +x scripts/*.sh

# Create systemd service file
echo -e "${YELLOW}Creating systemd service${NC}"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Task Scheduler - Background task management system
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py --config $INSTALL_DIR/config/config.yaml
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=task-scheduler

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo -e "${GREEN}Installation completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Configure tasks in: $INSTALL_DIR/tasks/"
echo "2. Modify configuration: $INSTALL_DIR/config/config.yaml"
echo "3. Start the service: systemctl start $SERVICE_NAME"
echo "4. Check status: systemctl status $SERVICE_NAME"
echo "5. View logs: journalctl -u $SERVICE_NAME -f"
