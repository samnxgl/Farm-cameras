"""
Configuration management for the Farm Camera Detection System.
Supports multiple cameras with different detection profiles.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class CameraConfig:
    """Configuration for a single camera."""

    name: str
    ip: str
    port: int
    username: str
    password: str
    channel: int
    profile: str  # Detection profile: "farm", "entrance"
    enabled: bool = True
    rtsp_url: str = ""  # Direct RTSP URL (if provided, uses RTSP instead of HTTP)
    connection_type: str = "http"  # "http" or "rtsp"

    def get_base_url(self) -> str:
        """Get the base URL for the camera."""
        return f"http://{self.ip}:{self.port}"

    def get_snapshot_url(self) -> str:
        """Get the URL for capturing a snapshot."""
        return f"{self.get_base_url()}/ISAPI/Streaming/channels/{self.channel}01/picture"

    def get_rtsp_url(self) -> str:
        """Get the RTSP URL for streaming."""
        if self.rtsp_url:
            # If credentials not in URL, add them
            if self.username and self.password and "@" not in self.rtsp_url:
                # Insert credentials into RTSP URL
                return self.rtsp_url.replace(
                    "rtsp://", f"rtsp://{self.username}:{self.password}@"
                )
            return self.rtsp_url
        # Construct from IP/port
        return (
            f"rtsp://{self.username}:{self.password}@"
            f"{self.ip}:554/Streaming/Channels/{self.channel}01"
        )

    def uses_rtsp(self) -> bool:
        """Check if this camera uses RTSP for capture."""
        return self.connection_type == "rtsp" or bool(self.rtsp_url)


class Config:
    """Application configuration loaded from environment variables."""

    # Anthropic API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Slack Settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#farm-alerts")

    # Application Settings
    CAPTURE_INTERVAL_SECONDS: int = int(os.getenv("CAPTURE_INTERVAL_SECONDS", "10"))
    SAVE_IMAGES: bool = os.getenv("SAVE_IMAGES", "true").lower() == "true"
    IMAGES_DIR: Path = Path(os.getenv("IMAGES_DIR", "./captured_images"))

    # Camera configurations (loaded dynamically)
    CAMERAS: list[CameraConfig] = []

    @classmethod
    def load_cameras(cls) -> list[CameraConfig]:
        """Load camera configurations from environment variables."""
        cameras = []

        # Camera 1 (Farm Camera) - supports legacy HIKVISION_* variables
        cam1_ip = os.getenv("CAMERA_1_IP", os.getenv("HIKVISION_IP", ""))
        if cam1_ip:
            cameras.append(
                CameraConfig(
                    name=os.getenv("CAMERA_1_NAME", "Farm Camera"),
                    ip=cam1_ip,
                    port=int(os.getenv("CAMERA_1_PORT", os.getenv("HIKVISION_PORT", "80"))),
                    username=os.getenv("CAMERA_1_USERNAME", os.getenv("HIKVISION_USERNAME", "admin")),
                    password=os.getenv("CAMERA_1_PASSWORD", os.getenv("HIKVISION_PASSWORD", "")),
                    channel=int(os.getenv("CAMERA_1_CHANNEL", os.getenv("HIKVISION_CHANNEL", "1"))),
                    profile=os.getenv("CAMERA_1_PROFILE", "farm"),
                    enabled=os.getenv("CAMERA_1_ENABLED", "true").lower() == "true",
                )
            )

        # Camera 2 (Home Entrance) - supports RTSP URL
        cam2_ip = os.getenv("CAMERA_2_IP", "")
        cam2_rtsp = os.getenv("CAMERA_2_RTSP_URL", "")
        if cam2_ip or cam2_rtsp:
            cameras.append(
                CameraConfig(
                    name=os.getenv("CAMERA_2_NAME", "Home Entrance"),
                    ip=cam2_ip,
                    port=int(os.getenv("CAMERA_2_PORT", "80")),
                    username=os.getenv("CAMERA_2_USERNAME", "admin"),
                    password=os.getenv("CAMERA_2_PASSWORD", ""),
                    channel=int(os.getenv("CAMERA_2_CHANNEL", "1")),
                    profile=os.getenv("CAMERA_2_PROFILE", "entrance"),
                    enabled=os.getenv("CAMERA_2_ENABLED", "true").lower() == "true",
                    rtsp_url=cam2_rtsp,
                    connection_type=os.getenv("CAMERA_2_CONNECTION", "rtsp" if cam2_rtsp else "http"),
                )
            )

        # Camera 3 (optional)
        cam3_ip = os.getenv("CAMERA_3_IP", "")
        if cam3_ip:
            cameras.append(
                CameraConfig(
                    name=os.getenv("CAMERA_3_NAME", "Camera 3"),
                    ip=cam3_ip,
                    port=int(os.getenv("CAMERA_3_PORT", "80")),
                    username=os.getenv("CAMERA_3_USERNAME", "admin"),
                    password=os.getenv("CAMERA_3_PASSWORD", ""),
                    channel=int(os.getenv("CAMERA_3_CHANNEL", "1")),
                    profile=os.getenv("CAMERA_3_PROFILE", "farm"),
                    enabled=os.getenv("CAMERA_3_ENABLED", "true").lower() == "true",
                )
            )

        cls.CAMERAS = cameras
        return cameras

    @classmethod
    def validate(cls) -> list[str]:
        """Validate that all required configuration is present."""
        errors = []

        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required")
        if not cls.SLACK_BOT_TOKEN:
            errors.append("SLACK_BOT_TOKEN is required")

        # Load cameras if not already loaded
        if not cls.CAMERAS:
            cls.load_cameras()

        if not cls.CAMERAS:
            errors.append("At least one camera must be configured")

        for cam in cls.CAMERAS:
            if not cam.ip and not cam.rtsp_url:
                errors.append(f"Camera '{cam.name}' is missing IP address or RTSP URL")
            if not cam.password and not cam.rtsp_url:
                errors.append(f"Camera '{cam.name}' is missing password")

        return errors

    @classmethod
    def get_enabled_cameras(cls) -> list[CameraConfig]:
        """Get list of enabled cameras."""
        if not cls.CAMERAS:
            cls.load_cameras()
        return [cam for cam in cls.CAMERAS if cam.enabled]
