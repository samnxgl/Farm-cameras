"""
Slack notification module.

Handles sending alerts with images to Slack channels.
"""

import io
import logging
from datetime import datetime
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import Config

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send notifications to Slack with optional image attachments."""

    def __init__(self):
        """Initialize the Slack client."""
        self.client = WebClient(token=Config.SLACK_BOT_TOKEN)
        self.channel = Config.SLACK_CHANNEL

    def send_alert(
        self,
        message: str,
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None,
    ) -> bool:
        """
        Send an alert to Slack with an optional image.

        Args:
            message: The alert message to send.
            image_data: Optional image data to upload.
            image_filename: Optional filename for the image.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        try:
            if image_data:
                return self._send_with_image(message, image_data, image_filename)
            else:
                return self._send_text_only(message)
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    def _send_text_only(self, message: str) -> bool:
        """Send a text-only message to Slack."""
        response = self.client.chat_postMessage(
            channel=self.channel,
            text=message,
            mrkdwn=True,
        )
        logger.info(f"Sent text message to Slack: {response['ts']}")
        return response["ok"]

    def _send_with_image(
        self,
        message: str,
        image_data: bytes,
        filename: Optional[str] = None,
    ) -> bool:
        """
        Send a message with an image to Slack.

        First uploads the image, then posts the message with the image attached.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"farm_camera_{timestamp}.jpg"

        # Upload the file to Slack
        response = self.client.files_upload_v2(
            channel=self.channel,
            file=io.BytesIO(image_data),
            filename=filename,
            initial_comment=message,
            title="Farm Camera Snapshot",
        )

        if response["ok"]:
            logger.info(f"Sent image alert to Slack: {filename}")
            return True
        else:
            logger.error(f"Failed to upload image to Slack: {response}")
            return False

    def send_startup_message(self) -> bool:
        """Send a startup notification to indicate the system is running."""
        message = (
            "🟢 *Farm Camera Monitor Started*\n\n"
            f"Monitoring camera at `{Config.HIKVISION_IP}` "
            f"every {Config.CAPTURE_INTERVAL_SECONDS} seconds.\n"
            "You will receive alerts when animals are detected."
        )
        return self.send_alert(message)

    def send_shutdown_message(self) -> bool:
        """Send a shutdown notification."""
        message = "🔴 *Farm Camera Monitor Stopped*"
        return self.send_alert(message)

    def send_error_message(self, error: str) -> bool:
        """Send an error notification."""
        message = f"⚠️ *Farm Camera Monitor Error*\n\n```{error}```"
        return self.send_alert(message)

    def test_connection(self) -> bool:
        """
        Test the Slack connection.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            response = self.client.auth_test()
            if response["ok"]:
                logger.info(
                    f"Slack connection successful. Bot: {response['user']}"
                )
                return True
            return False
        except SlackApiError as e:
            logger.error(f"Slack connection test failed: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False
