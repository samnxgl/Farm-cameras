"""
Camera integration module.

Supports capturing snapshots via:
- ISAPI HTTP interface (Hikvision cameras)
- RTSP streams (any RTSP-capable camera)
"""

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import requests
from requests.auth import HTTPDigestAuth

from config import CameraConfig, Config

logger = logging.getLogger(__name__)


class HikvisionCamera:
    """Client for interacting with IP cameras via HTTP or RTSP."""

    def __init__(self, camera_config: CameraConfig):
        """Initialize the camera client with configuration."""
        self.config = camera_config
        self.name = camera_config.name
        self.uses_rtsp = camera_config.uses_rtsp()

        if self.uses_rtsp:
            self.rtsp_url = camera_config.get_rtsp_url()
            logger.info(f"[{self.name}] Using RTSP connection")
        else:
            self.base_url = camera_config.get_base_url()
            self.snapshot_url = camera_config.get_snapshot_url()
            self.auth = HTTPDigestAuth(
                camera_config.username,
                camera_config.password
            )
            self.session = requests.Session()
            self.session.auth = self.auth
            logger.info(f"[{self.name}] Using HTTP connection")

        self.timeout = 10  # seconds

    def capture_snapshot(self) -> Optional[bytes]:
        """
        Capture a snapshot from the camera.

        Returns:
            The image data as bytes (JPEG), or None if capture failed.
        """
        if self.uses_rtsp:
            return self._capture_rtsp()
        else:
            return self._capture_http()

    def _capture_http(self) -> Optional[bytes]:
        """Capture snapshot via HTTP ISAPI interface."""
        try:
            logger.info(f"[{self.name}] Capturing via HTTP: {self.snapshot_url}")
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

    def _capture_rtsp(self) -> Optional[bytes]:
        """Capture a single frame from RTSP stream."""
        cap = None
        try:
            logger.info(f"[{self.name}] Capturing via RTSP stream")

            # Open RTSP stream
            cap = cv2.VideoCapture(self.rtsp_url)

            if not cap.isOpened():
                logger.error(f"[{self.name}] Failed to open RTSP stream")
                return None

            # Set timeout (in milliseconds)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout * 1000)

            # Read a frame
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.error(f"[{self.name}] Failed to read frame from RTSP stream")
                return None

            # Encode frame as JPEG
            success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            if not success:
                logger.error(f"[{self.name}] Failed to encode frame as JPEG")
                return None

            image_data = buffer.tobytes()
            logger.info(f"[{self.name}] Captured RTSP frame: {len(image_data)} bytes")
            return image_data

        except Exception as e:
            logger.error(f"[{self.name}] Error capturing RTSP frame: {e}")
            return None
        finally:
            if cap is not None:
                cap.release()

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
        if self.uses_rtsp:
            return self._test_rtsp_connection()
        else:
            return self._test_http_connection()

    def _test_http_connection(self) -> bool:
        """Test HTTP connection to camera."""
        try:
            device_info_url = f"{self.base_url}/ISAPI/System/deviceInfo"
            response = self.session.get(device_info_url, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"[{self.name}] HTTP connection test successful")
            return True
        except Exception as e:
            logger.error(f"[{self.name}] HTTP connection test failed: {e}")
            return False

    def _test_rtsp_connection(self) -> bool:
        """Test RTSP connection to camera."""
        cap = None
        try:
            cap = cv2.VideoCapture(self.rtsp_url)

            if not cap.isOpened():
                logger.error(f"[{self.name}] RTSP connection test failed: cannot open stream")
                return False

            # Try to read one frame
            ret, frame = cap.read()

            if ret and frame is not None:
                logger.info(f"[{self.name}] RTSP connection test successful")
                return True
            else:
                logger.error(f"[{self.name}] RTSP connection test failed: cannot read frame")
                return False

        except Exception as e:
            logger.error(f"[{self.name}] RTSP connection test failed: {e}")
            return False
        finally:
            if cap is not None:
                cap.release()

    def close(self):
        """Close the session."""
        if not self.uses_rtsp and hasattr(self, 'session'):
            self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
