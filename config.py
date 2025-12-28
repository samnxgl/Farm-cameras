"""
Configuration management for the Farm Camera Animal Detection System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # Hikvision Camera Settings
    HIKVISION_IP: str = os.getenv("HIKVISION_IP", "192.168.1.100")
    HIKVISION_PORT: int = int(os.getenv("HIKVISION_PORT", "80"))
    HIKVISION_USERNAME: str = os.getenv("HIKVISION_USERNAME", "admin")
    HIKVISION_PASSWORD: str = os.getenv("HIKVISION_PASSWORD", "")
    HIKVISION_CHANNEL: int = int(os.getenv("HIKVISION_CHANNEL", "1"))

    # Anthropic API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Slack Settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#farm-alerts")

    # Application Settings
    CAPTURE_INTERVAL_SECONDS: int = int(os.getenv("CAPTURE_INTERVAL_SECONDS", "10"))
    SAVE_IMAGES: bool = os.getenv("SAVE_IMAGES", "true").lower() == "true"
    IMAGES_DIR: Path = Path(os.getenv("IMAGES_DIR", "./captured_images"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate that all required configuration is present."""
        errors = []

        if not cls.HIKVISION_IP:
            errors.append("HIKVISION_IP is required")
        if not cls.HIKVISION_PASSWORD:
            errors.append("HIKVISION_PASSWORD is required")
        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required")
        if not cls.SLACK_BOT_TOKEN:
            errors.append("SLACK_BOT_TOKEN is required")

        return errors

    @classmethod
    def get_camera_base_url(cls) -> str:
        """Get the base URL for the Hikvision camera."""
        return f"http://{cls.HIKVISION_IP}:{cls.HIKVISION_PORT}"

    @classmethod
    def get_snapshot_url(cls) -> str:
        """Get the URL for capturing a snapshot from the camera."""
        return (
            f"{cls.get_camera_base_url()}/ISAPI/Streaming/channels/"
            f"{cls.HIKVISION_CHANNEL}01/picture"
        )

    @classmethod
    def get_rtsp_url(cls) -> str:
        """Get the RTSP URL for streaming (alternative method)."""
        return (
            f"rtsp://{cls.HIKVISION_USERNAME}:{cls.HIKVISION_PASSWORD}@"
            f"{cls.HIKVISION_IP}:554/Streaming/Channels/{cls.HIKVISION_CHANNEL}01"
        )
