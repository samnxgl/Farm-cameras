"""
Animal detection module using Claude's vision capabilities.

Uses Anthropic's Claude API to analyze images and detect animals.
"""

import base64
import logging
from dataclasses import dataclass
from typing import Optional

import anthropic

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of an animal/vehicle detection analysis."""

    animals_detected: bool
    vehicles_detected: bool
    description: str
    animal_types: list[str]
    vehicle_types: list[str]
    confidence: str  # "high", "medium", "low"
    details: str


class AnimalDetector:
    """Detect animals in images using Claude's vision API."""

    DETECTION_PROMPT = """Analyze this image from a farm security camera. Your task is to identify if there are any animals or vehicles visible in the image.

Please respond in the following exact format:

ANIMALS_DETECTED: [YES/NO]
VEHICLES_DETECTED: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
ANIMAL_TYPES: [comma-separated list of animal types, or "none" if no animals]
VEHICLE_TYPES: [comma-separated list of vehicle types, or "none" if no vehicles]
DESCRIPTION: [A brief 1-2 sentence description of what you see and what's happening]
DETAILS: [Any additional relevant details - size, behavior, location in frame, potential concerns]

Focus on:
- Farm animals (cows, horses, pigs, sheep, goats, chickens, etc.)
- Wildlife (deer, foxes, coyotes, bears, wolves, raccoons, etc.)
- Pets (dogs, cats)
- Birds
- Any other animals
- Vehicles (cars, trucks, tractors, ATVs, motorcycles, vans, SUVs, etc.)

If nothing notable is present, still provide a brief description of what you see in the image (e.g., "Empty farmyard with barn visible" or "Night scene with no visible movement").

Be accurate and only report animals/vehicles you can clearly identify in the image."""

    def __init__(self):
        """Initialize the detector with Anthropic client."""
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    def analyze_image(self, image_data: bytes) -> Optional[DetectionResult]:
        """
        Analyze an image for animal detection.

        Args:
            image_data: The image data as bytes (JPEG format).

        Returns:
            DetectionResult if analysis succeeded, None otherwise.
        """
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            logger.info("Sending image to Claude for analysis...")

            # Call Claude API with the image
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                            {
                                "type": "text",
                                "text": self.DETECTION_PROMPT,
                            },
                        ],
                    }
                ],
            )

            # Parse the response
            response_text = message.content[0].text
            logger.debug(f"Claude response: {response_text}")

            return self._parse_response(response_text)

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return None

    def _parse_response(self, response_text: str) -> DetectionResult:
        """
        Parse the structured response from Claude.

        Args:
            response_text: The raw response text from Claude.

        Returns:
            A DetectionResult object.
        """
        lines = response_text.strip().split("\n")

        animals_detected = False
        vehicles_detected = False
        confidence = "low"
        animal_types = []
        vehicle_types = []
        description = ""
        details = ""

        for line in lines:
            line = line.strip()
            if line.startswith("ANIMALS_DETECTED:"):
                value = line.split(":", 1)[1].strip().upper()
                animals_detected = value == "YES"
            elif line.startswith("VEHICLES_DETECTED:"):
                value = line.split(":", 1)[1].strip().upper()
                vehicles_detected = value == "YES"
            elif line.startswith("CONFIDENCE:"):
                confidence = line.split(":", 1)[1].strip().lower()
            elif line.startswith("ANIMAL_TYPES:"):
                types_str = line.split(":", 1)[1].strip()
                if types_str.lower() != "none":
                    animal_types = [t.strip() for t in types_str.split(",")]
            elif line.startswith("VEHICLE_TYPES:"):
                types_str = line.split(":", 1)[1].strip()
                if types_str.lower() != "none":
                    vehicle_types = [t.strip() for t in types_str.split(",")]
            elif line.startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip()
            elif line.startswith("DETAILS:"):
                details = line.split(":", 1)[1].strip()

        return DetectionResult(
            animals_detected=animals_detected,
            vehicles_detected=vehicles_detected,
            description=description or "No description available",
            animal_types=animal_types,
            vehicle_types=vehicle_types,
            confidence=confidence,
            details=details or "No additional details",
        )


def format_detection_message(result: DetectionResult) -> str:
    """
    Format a detection result as a human-readable message.

    Args:
        result: The detection result to format.

    Returns:
        A formatted message string.
    """
    if not result.animals_detected and not result.vehicles_detected:
        return "No animals or vehicles detected in the image."

    parts = []

    if result.animals_detected:
        animal_list = ", ".join(result.animal_types) if result.animal_types else "Unknown"
        parts.append(f"*Animals Spotted:* {animal_list}")

    if result.vehicles_detected:
        vehicle_list = ", ".join(result.vehicle_types) if result.vehicle_types else "Unknown"
        parts.append(f"*Vehicles Spotted:* {vehicle_list}")

    # Determine alert type
    if result.animals_detected and result.vehicles_detected:
        header = "🚨 *Animal & Vehicle Detected on Farm Camera*"
    elif result.animals_detected:
        header = "🚨 *Animal Detected on Farm Camera*"
    else:
        header = "🚗 *Vehicle Detected on Farm Camera*"

    spotted_info = "\n".join(parts)

    message = f"""{header}

{spotted_info}
*Confidence:* {result.confidence.capitalize()}

*Description:* {result.description}

*Details:* {result.details}"""

    return message
