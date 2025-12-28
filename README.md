# Farm Camera Animal Detection System

A Python-based monitoring system that connects to Hikvision IP cameras, uses AI to detect animals in the live feed, and sends Slack alerts with images when animals are spotted.

## Features

- **Hikvision Camera Integration**: Captures snapshots from Hikvision IP cameras using the ISAPI interface
- **AI-Powered Animal Detection**: Uses Claude's vision capabilities to identify animals in images
- **Slack Notifications**: Sends real-time alerts with animal descriptions and images to your Slack channel
- **Configurable Monitoring**: Adjustable capture intervals and image storage options
- **Graceful Shutdown**: Handles SIGINT/SIGTERM for clean shutdown

## Prerequisites

- Python 3.10 or higher
- A Hikvision IP camera accessible on your network
- An Anthropic API key (for Claude vision API)
- A Slack workspace with a bot configured

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Farm-cameras
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the example environment file and configure it:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your configuration (see Configuration section below)

## Configuration

Edit the `.env` file with your settings:

```env
# Hikvision Camera Configuration
HIKVISION_IP=192.168.1.100        # Your camera's IP address
HIKVISION_PORT=80                  # HTTP port (usually 80)
HIKVISION_USERNAME=admin           # Camera username
HIKVISION_PASSWORD=your_password   # Camera password
HIKVISION_CHANNEL=1                # Camera channel (usually 1)

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...       # Your Anthropic API key

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-...           # Your Slack bot token
SLACK_CHANNEL=#farm-alerts         # Channel for alerts

# Application Settings
CAPTURE_INTERVAL_SECONDS=10        # How often to capture (default: 10)
SAVE_IMAGES=true                   # Save images locally
IMAGES_DIR=./captured_images       # Where to save images
```

### Setting Up Slack Bot

1. Go to [Slack API](https://api.slack.com/apps) and create a new app
2. Under "OAuth & Permissions", add these scopes:
   - `chat:write` - Send messages
   - `files:write` - Upload images
3. Install the app to your workspace
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
5. Invite the bot to your alert channel: `/invite @YourBotName`

### Getting Anthropic API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or sign in
3. Generate an API key under Settings > API Keys

## Usage

### Start Monitoring

```bash
python main.py
```

The system will:
1. Test connections to your camera and Slack
2. Send a startup message to Slack
3. Begin capturing images every 10 seconds
4. Send alerts when animals are detected

### Command Line Options

```bash
# Run a single capture cycle (good for testing)
python main.py --single

# Test camera connection only
python main.py --test-camera

# Test Slack connection only
python main.py --test-slack

# Skip startup/shutdown Slack messages
python main.py --no-startup-message

# Enable debug logging
python main.py --debug
```

### Running as a Service

To run the monitor as a background service on Linux, create a systemd service:

```ini
# /etc/systemd/system/farm-monitor.service
[Unit]
Description=Farm Camera Animal Detection
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/Farm-cameras
Environment=PATH=/path/to/Farm-cameras/venv/bin
ExecStart=/path/to/Farm-cameras/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl enable farm-monitor
sudo systemctl start farm-monitor
```

## Project Structure

```
Farm-cameras/
├── main.py           # Main application entry point
├── camera.py         # Hikvision camera integration
├── detector.py       # Animal detection using Claude AI
├── notifier.py       # Slack notification handling
├── config.py         # Configuration management
├── requirements.txt  # Python dependencies
├── .env.example      # Example environment configuration
├── .gitignore        # Git ignore rules
└── README.md         # This file
```

## How It Works

1. **Image Capture**: The system connects to your Hikvision camera using HTTP Digest Authentication and captures JPEG snapshots through the ISAPI interface.

2. **AI Analysis**: Each image is sent to Claude's vision API with a specialized prompt for animal detection. Claude analyzes the image and returns structured data about any animals found.

3. **Alert Generation**: When animals are detected, the system formats an alert message including:
   - Types of animals spotted
   - Confidence level
   - Description of what they're doing
   - The original image

4. **Slack Notification**: The alert and image are uploaded to your configured Slack channel so you can monitor from anywhere.

## Troubleshooting

### Camera Connection Failed
- Verify the camera IP address is correct and reachable
- Check that the username/password are correct
- Ensure the camera's HTTP service is enabled
- Try accessing `http://<camera-ip>/ISAPI/System/deviceInfo` in a browser

### Slack Messages Not Sending
- Verify the bot token is correct
- Ensure the bot is invited to the target channel
- Check that the channel name includes the # prefix

### No Animals Being Detected
- Verify images are being captured (check `captured_images/` folder)
- Try running with `--debug` to see analysis results
- Ensure your Anthropic API key has sufficient credits

## License

MIT License
