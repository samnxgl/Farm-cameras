#!/bin/bash
#
# Farm Camera Animal Detection - Automated Setup Script
# Run this on your cloud server to install and configure the service
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Farm Camera Animal Detection Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Will create a dedicated user.${NC}"
    INSTALL_USER="farmcam"
    INSTALL_DIR="/opt/farm-camera"
else
    INSTALL_USER="$USER"
    INSTALL_DIR="$HOME/farm-camera"
fi

echo -e "\n${GREEN}[1/6] Installing system dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv git
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip git
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip git
else
    echo -e "${RED}Unsupported package manager. Please install Python 3 manually.${NC}"
    exit 1
fi

echo -e "\n${GREEN}[2/6] Creating installation directory...${NC}"
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$INSTALL_USER:$INSTALL_USER" "$INSTALL_DIR" 2>/dev/null || true

echo -e "\n${GREEN}[3/6] Copying application files...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

echo -e "\n${GREEN}[4/6] Setting up Python virtual environment...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo -e "\n${GREEN}[5/6] Setting up configuration...${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo -e "${YELLOW}Creating .env file - you'll need to configure this!${NC}"
    cat > "$INSTALL_DIR/.env" << 'EOF'
# Hikvision Camera Configuration
HIKVISION_IP=169.255.172.209
HIKVISION_PORT=84
HIKVISION_USERNAME=admin
HIKVISION_PASSWORD=YOUR_CAMERA_PASSWORD

# Anthropic API for animal detection
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY

# Slack Configuration
SLACK_BOT_TOKEN=YOUR_SLACK_BOT_TOKEN
SLACK_CHANNEL=#sam-farm-cam-alerts

# Application Settings
CAPTURE_INTERVAL_SECONDS=10
SAVE_IMAGES=true
IMAGES_DIR=./captured_images
EOF
    chmod 600 "$INSTALL_DIR/.env"
    echo -e "${YELLOW}Please edit $INSTALL_DIR/.env with your credentials${NC}"
fi

echo -e "\n${GREEN}[6/6] Setting up systemd service...${NC}"
SERVICE_FILE="/etc/systemd/system/farm-camera.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Farm Camera Animal Detection Service
After=network.target

[Service]
Type=simple
User=$INSTALL_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable farm-camera

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nInstallation directory: ${YELLOW}$INSTALL_DIR${NC}"
echo -e "\nNext steps:"
echo -e "  1. Edit configuration: ${YELLOW}nano $INSTALL_DIR/.env${NC}"
echo -e "  2. Test camera:        ${YELLOW}cd $INSTALL_DIR && source venv/bin/activate && python main.py --test-camera${NC}"
echo -e "  3. Test Slack:         ${YELLOW}cd $INSTALL_DIR && source venv/bin/activate && python main.py --test-slack${NC}"
echo -e "  4. Start service:      ${YELLOW}sudo systemctl start farm-camera${NC}"
echo -e "  5. Check status:       ${YELLOW}sudo systemctl status farm-camera${NC}"
echo -e "  6. View logs:          ${YELLOW}sudo journalctl -u farm-camera -f${NC}"
echo ""
