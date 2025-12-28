#!/bin/bash
#
# One-line cloud deployment script
# Usage: curl -sSL <raw-url>/deploy-cloud.sh | bash
#
# Or run directly on your server after cloning
#

set -e

REPO_URL="https://github.com/samnxgl/Farm-cameras.git"
BRANCH="claude/hikvision-animal-detection-QFXA5"
INSTALL_DIR="/opt/farm-camera"

echo "🚀 Farm Camera Animal Detection - Cloud Deployment"
echo "=================================================="

# Check for required tools
command -v git >/dev/null 2>&1 || { echo "❌ Git is required. Install with: sudo apt install git"; exit 1; }

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git pull origin "$BRANCH"
else
    echo "📥 Cloning repository..."
    sudo git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    sudo chown -R $USER:$USER "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Run setup
chmod +x setup.sh
./setup.sh

echo ""
echo "✅ Deployment complete!"
