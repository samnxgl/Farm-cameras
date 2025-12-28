#!/usr/bin/env python3
"""
Multi-Camera Detection System

Monitors multiple Hikvision cameras with different detection profiles
and sends Slack alerts when relevant activity is detected.
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Optional

from camera import HikvisionCamera
from config import CameraConfig, Config
from detector import Detector, format_detection_message, should_alert
from notifier import SlackNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("farm_monitor.log"),
    ],
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def validate_configuration() -> bool:
    """Validate all required configuration is present."""
    errors = Config.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        return False
    return True


def process_camera(
    camera: HikvisionCamera,
    detector: Detector,
    notifier: SlackNotifier,
) -> None:
    """
    Capture and process a single snapshot from a camera.

    Args:
        camera: The camera to capture from.
        detector: The detector to analyze images.
        notifier: The notifier to send alerts.
    """
    camera_name = camera.name
    profile = camera.config.profile

    # Capture snapshot
    image_data = camera.capture_snapshot()
    if image_data is None:
        logger.warning(f"[{camera_name}] Failed to capture snapshot, skipping")
        return

    # Optionally save the image
    if Config.SAVE_IMAGES:
        camera.save_snapshot(image_data)

    # Analyze image with the camera's profile
    logger.info(f"[{camera_name}] Analyzing image with '{profile}' profile...")
    result = detector.analyze_image(image_data, profile=profile)

    if result is None:
        logger.warning(f"[{camera_name}] Failed to analyze image, skipping")
        return

    # Check if we should alert based on profile
    if should_alert(result, profile):
        # Log what was detected
        detected = []
        if result.people_detected:
            detected.append(f"{result.people_count} person(s)")
        if result.animals_detected:
            detected.append(f"animals: {', '.join(result.animal_types)}")
        if result.vehicles_detected:
            detected.append(f"vehicles: {', '.join(result.vehicle_types)}")

        logger.info(
            f"[{camera_name}] Detected: {', '.join(detected)} "
            f"(confidence: {result.confidence})"
        )

        # Format and send alert
        message = format_detection_message(result, camera_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = camera_name.lower().replace(" ", "_")
        filename = f"{safe_name}_{timestamp}.jpg"

        if notifier.send_alert(message, image_data, filename):
            logger.info(f"[{camera_name}] Alert sent to Slack")
        else:
            logger.error(f"[{camera_name}] Failed to send alert to Slack")
    else:
        logger.info(f"[{camera_name}] No relevant activity detected")


def run_monitor(skip_startup_message: bool = False) -> None:
    """Run the main monitoring loop for all cameras."""
    global running

    logger.info("Starting Multi-Camera Detection System")
    logger.info(f"Capture interval: {Config.CAPTURE_INTERVAL_SECONDS} seconds")
    logger.info(f"Slack channel: {Config.SLACK_CHANNEL}")

    # Load camera configurations
    cameras_config = Config.get_enabled_cameras()
    if not cameras_config:
        logger.error("No cameras configured. Exiting.")
        sys.exit(1)

    logger.info(f"Loaded {len(cameras_config)} camera(s):")
    for cam in cameras_config:
        logger.info(f"  - {cam.name} ({cam.ip}:{cam.port}) [profile: {cam.profile}]")

    # Initialize cameras
    cameras: list[HikvisionCamera] = []
    for cam_config in cameras_config:
        cameras.append(HikvisionCamera(cam_config))

    # Initialize detector and notifier
    detector = Detector()
    notifier = SlackNotifier()

    try:
        # Test Slack connection
        logger.info("Testing Slack connection...")
        if not notifier.test_connection():
            logger.error("Failed to connect to Slack")
            sys.exit(1)
        logger.info("Slack connection successful")

        # Test camera connections
        for camera in cameras:
            logger.info(f"Testing connection to {camera.name}...")
            if camera.test_connection():
                logger.info(f"{camera.name}: Connection successful")
            else:
                logger.warning(f"{camera.name}: Connection failed - will retry during monitoring")

        # Send startup message
        if not skip_startup_message:
            camera_list = ", ".join([c.name for c in cameras])
            notifier.send_startup_message(camera_list)

        logger.info("Starting monitoring loop...")

        # Main loop
        while running:
            for camera in cameras:
                if not running:
                    break
                try:
                    process_camera(camera, detector, notifier)
                except Exception as e:
                    logger.error(f"[{camera.name}] Error in processing: {e}")

            # Wait for next cycle
            if running:
                logger.debug(f"Waiting {Config.CAPTURE_INTERVAL_SECONDS} seconds...")
                for _ in range(Config.CAPTURE_INTERVAL_SECONDS * 10):
                    if not running:
                        break
                    time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Cleanup
        logger.info("Shutting down...")
        if not skip_startup_message:
            try:
                notifier.send_shutdown_message()
            except Exception:
                pass
        for camera in cameras:
            camera.close()
        logger.info("Shutdown complete")


def run_single_capture(camera_name: Optional[str] = None) -> None:
    """Run a single capture cycle for one or all cameras."""
    logger.info("Running single capture mode")

    cameras_config = Config.get_enabled_cameras()
    if camera_name:
        cameras_config = [c for c in cameras_config if c.name.lower() == camera_name.lower()]
        if not cameras_config:
            logger.error(f"Camera '{camera_name}' not found")
            sys.exit(1)

    detector = Detector()
    notifier = SlackNotifier()

    if not notifier.test_connection():
        logger.error("Failed to connect to Slack")
        sys.exit(1)

    for cam_config in cameras_config:
        camera = HikvisionCamera(cam_config)
        try:
            if camera.test_connection():
                process_camera(camera, detector, notifier)
            else:
                logger.error(f"[{camera.name}] Connection test failed")
        finally:
            camera.close()

    logger.info("Single capture completed")


def test_cameras() -> bool:
    """Test connection to all cameras."""
    cameras_config = Config.get_enabled_cameras()
    if not cameras_config:
        logger.error("No cameras configured")
        return False

    all_success = True
    for cam_config in cameras_config:
        camera = HikvisionCamera(cam_config)
        try:
            if camera.test_connection():
                logger.info(f"✓ {cam_config.name}: Connection successful")
            else:
                logger.error(f"✗ {cam_config.name}: Connection failed")
                all_success = False
        finally:
            camera.close()

    return all_success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Camera Detection System"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run a single capture cycle and exit",
    )
    parser.add_argument(
        "--camera",
        type=str,
        help="Specify camera name for single capture (default: all)",
    )
    parser.add_argument(
        "--test-cameras",
        action="store_true",
        help="Test all camera connections and exit",
    )
    parser.add_argument(
        "--test-slack",
        action="store_true",
        help="Test Slack connection and exit",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="List configured cameras and exit",
    )
    parser.add_argument(
        "--no-startup-message",
        action="store_true",
        help="Skip sending startup/shutdown messages to Slack",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate configuration
    if not validate_configuration():
        logger.error(
            "Configuration validation failed. "
            "Please check your .env file and try again."
        )
        sys.exit(1)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run appropriate mode
    if args.list_cameras:
        cameras = Config.get_enabled_cameras()
        print(f"\nConfigured Cameras ({len(cameras)}):")
        print("-" * 50)
        for cam in cameras:
            status = "enabled" if cam.enabled else "disabled"
            print(f"  {cam.name}")
            print(f"    IP: {cam.ip}:{cam.port}")
            print(f"    Profile: {cam.profile}")
            print(f"    Status: {status}")
            print()
        sys.exit(0)

    elif args.test_cameras:
        success = test_cameras()
        sys.exit(0 if success else 1)

    elif args.test_slack:
        notifier = SlackNotifier()
        success = notifier.test_connection()
        sys.exit(0 if success else 1)

    elif args.single:
        run_single_capture(args.camera)

    else:
        run_monitor(skip_startup_message=args.no_startup_message)


if __name__ == "__main__":
    main()
