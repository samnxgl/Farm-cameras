"""
Hikvision camera integration module.

Supports capturing snapshots via the ISAPI HTTP interface.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.auth import HTTPDigestAuth

from config import CameraConfig, Config

logger = logging.getLogger(__name__)


class HikvisionCamera:
    """Client for interacting with Hikvision IP cameras."""

    def __init__(self, camera_config: CameraConfig):
        """Initialize the camera client with configuration."""
        self.config = camera_config
        self.name = camera_config.name
        self.base_url = camera_config.get_base_url()
        self.snapshot_url = camera_config.get_snapshot_url()
        self.auth = HTTPDigestAuth(
            camera_config.username,
            camera_config.password
        )
        self.session = requests.Session()
        self.session.auth = self.auth
        self.timeout = 10  # seconds

    def capture_snapshot(self) -> Optional[bytes]:
        """
        Capture a snapshot from the camera.

        Returns:
            The image data as bytes, or None if capture failed.
        """
        try:
            logger.info(f"[{self.name}] Capturing snapshot from {self.snapshot_url}")
            response = self.session.get(
                self.snapshot_url,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()

            # Verify we got an image
            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type.lower():
                logger.error(
                    f"[{self.name}] Unexpected content type: {content_type}. "
                    "Expected an image."
                )
                return None

            image_data = response.content
            logger.info(f"[{self.name}] Captured snapshot: {len(image_data)} bytes")
            return image_data

        except requests.exceptions.Timeout:
            logger.error(f"[{self.name}] Timeout while capturing snapshot")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[{self.name}] Connection error: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"[{self.name}] HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.name}] Unexpected error capturing snapshot: {e}")
            return None

    def save_snapshot(
        self,
        image_data: bytes,
        directory: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Save a snapshot to disk.

        Args:
            image_data: The image data as bytes.
            directory: The directory to save to (defaults to Config.IMAGES_DIR).

        Returns:
            The path to the saved image, or None if save failed.
        """
        if directory is None:
            directory = Config.IMAGES_DIR

        try:
            # Create camera-specific subdirectory
            camera_dir = directory / self.name.lower().replace(" ", "_")
            camera_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}.jpg"
            filepath = camera_dir / filename

            # Write image to disk
            with open(filepath, "wb") as f:
                f.write(image_data)

            logger.info(f"[{self.name}] Saved snapshot to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"[{self.name}] Error saving snapshot: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test the connection to the camera.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            # Try to access the device info endpoint
            device_info_url = f"{self.base_url}/ISAPI/System/deviceInfo"
            response = self.session.get(device_info_url, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"[{self.name}] Connection test successful")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] Connection test failed: {e}")
            return False

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
