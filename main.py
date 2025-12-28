#!/usr/bin/env python3
"""
Farm Camera Animal Detection System

Monitors a Hikvision camera for animals and sends Slack alerts when detected.
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime

from camera import HikvisionCamera
from config import Config
from detector import AnimalDetector, format_detection_message
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


def test_connections(
    camera: HikvisionCamera,
    notifier: SlackNotifier,
) -> bool:
    """Test connections to camera and Slack."""
    logger.info("Testing camera connection...")
    if not camera.test_connection():
        logger.error("Failed to connect to camera")
        return False
    logger.info("Camera connection successful")

    logger.info("Testing Slack connection...")
    if not notifier.test_connection():
        logger.error("Failed to connect to Slack")
        return False
    logger.info("Slack connection successful")

    return True


def process_snapshot(
    camera: HikvisionCamera,
    detector: AnimalDetector,
    notifier: SlackNotifier,
) -> None:
    """
    Capture and process a single snapshot.

    Captures image, analyzes for animals, and sends alert if detected.
    """
    # Capture snapshot
    image_data = camera.capture_snapshot()
    if image_data is None:
        logger.warning("Failed to capture snapshot, skipping this cycle")
        return

    # Optionally save the image
    if Config.SAVE_IMAGES:
        camera.save_snapshot(image_data)

    # Analyze for animals and vehicles
    logger.info("Analyzing image for animals and vehicles...")
    result = detector.analyze_image(image_data)

    if result is None:
        logger.warning("Failed to analyze image, skipping this cycle")
        return

    # Log the result and send alerts
    if result.animals_detected or result.vehicles_detected:
        if result.animals_detected:
            logger.info(
                f"Animals detected: {', '.join(result.animal_types)} "
                f"(confidence: {result.confidence})"
            )
        if result.vehicles_detected:
            logger.info(
                f"Vehicles detected: {', '.join(result.vehicle_types)} "
                f"(confidence: {result.confidence})"
            )

        # Format and send alert
        message = format_detection_message(result)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"detection_{timestamp}.jpg"

        if notifier.send_alert(message, image_data, filename):
            logger.info("Alert sent to Slack successfully")
        else:
            logger.error("Failed to send alert to Slack")
    else:
        logger.info("No animals or vehicles detected in this snapshot")


def run_monitor(skip_startup_message: bool = False) -> None:
    """Run the main monitoring loop."""
    global running

    logger.info("Starting Farm Camera Animal Detection System")
    logger.info(f"Camera IP: {Config.HIKVISION_IP}")
    logger.info(f"Capture interval: {Config.CAPTURE_INTERVAL_SECONDS} seconds")
    logger.info(f"Slack channel: {Config.SLACK_CHANNEL}")

    # Initialize components
    camera = HikvisionCamera()
    detector = AnimalDetector()
    notifier = SlackNotifier()

    try:
        # Test connections
        if not test_connections(camera, notifier):
            logger.error("Connection tests failed, exiting")
            sys.exit(1)

        # Send startup message
        if not skip_startup_message:
            notifier.send_startup_message()

        logger.info("Starting monitoring loop...")

        # Main loop
        while running:
            try:
                process_snapshot(camera, detector, notifier)
            except Exception as e:
                logger.error(f"Error in processing cycle: {e}")
                notifier.send_error_message(str(e))

            # Wait for next cycle
            if running:
                logger.debug(
                    f"Waiting {Config.CAPTURE_INTERVAL_SECONDS} seconds..."
                )
                # Use small sleep intervals to allow for quicker shutdown
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
        camera.close()
        logger.info("Shutdown complete")


def run_single_capture() -> None:
    """Run a single capture cycle (useful for testing)."""
    logger.info("Running single capture mode")

    camera = HikvisionCamera()
    detector = AnimalDetector()
    notifier = SlackNotifier()

    try:
        if not test_connections(camera, notifier):
            logger.error("Connection tests failed")
            sys.exit(1)

        process_snapshot(camera, detector, notifier)
        logger.info("Single capture completed")

    finally:
        camera.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Farm Camera Animal Detection System"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run a single capture cycle and exit",
    )
    parser.add_argument(
        "--test-camera",
        action="store_true",
        help="Test camera connection and exit",
    )
    parser.add_argument(
        "--test-slack",
        action="store_true",
        help="Test Slack connection and exit",
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
    if args.test_camera:
        camera = HikvisionCamera()
        success = camera.test_connection()
        camera.close()
        sys.exit(0 if success else 1)

    elif args.test_slack:
        notifier = SlackNotifier()
        success = notifier.test_connection()
        sys.exit(0 if success else 1)

    elif args.single:
        run_single_capture()

    else:
        run_monitor(skip_startup_message=args.no_startup_message)


if __name__ == "__main__":
    main()
