"""
Detection module using Claude's vision capabilities.

Supports multiple detection profiles for different camera use cases.
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
    """Result of a detection analysis."""

    animals_detected: bool
    vehicles_detected: bool
    people_detected: bool
    description: str
    animal_types: list[str]
    vehicle_types: list[str]
    people_count: int
    confidence: str  # "high", "medium", "low"
    details: str
    profile: str  # Which detection profile was used


# Detection prompts for different profiles
DETECTION_PROMPTS = {
    "farm": """Analyze this image from a farm security camera. Your task is to identify if there are any animals or vehicles visible in the image.

Please respond in the following exact format:

ANIMALS_DETECTED: [YES/NO]
VEHICLES_DETECTED: [YES/NO]
PEOPLE_DETECTED: [YES/NO]
PEOPLE_COUNT: [number of people visible, or 0]
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

If nothing notable is present, still provide a brief description of what you see in the image.

Be accurate and only report what you can clearly identify in the image.""",

    "entrance": """Analyze this image from a home entrance security camera. Your task is to identify and describe any people, vehicles, or animals visible in the image.

Please respond in the following exact format:

PEOPLE_DETECTED: [YES/NO]
PEOPLE_COUNT: [number of people visible, or 0]
VEHICLES_DETECTED: [YES/NO]
ANIMALS_DETECTED: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
VEHICLE_TYPES: [comma-separated list of vehicle types, or "none" if no vehicles]
ANIMAL_TYPES: [comma-separated list of animal types, or "none" if no animals]
DESCRIPTION: [A detailed 2-3 sentence description of what you see - describe people's appearance, clothing, actions, and any vehicles or animals present]
DETAILS: [Any additional relevant details - time of day indicators, suspicious behavior, packages being carried, direction of movement, etc.]

For people, describe:
- Approximate number of people
- General appearance (clothing colors, any distinctive features visible)
- What they appear to be doing (walking, standing, carrying packages, etc.)
- Direction of movement if apparent

For vehicles, note:
- Type of vehicle (car, truck, van, motorcycle, bicycle, etc.)
- Color if visible
- Whether it's parked, arriving, or leaving

For animals, note:
- Type of animal (dog, cat, wildlife, etc.)
- Size and behavior

If nothing notable is present, describe the current state of the entrance area.

Be accurate, detailed, and only report what you can clearly see in the image.""",
}


class Detector:
    """Detect objects in images using Claude's vision API."""

    def __init__(self):
        """Initialize the detector with Anthropic client."""
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

    def analyze_image(
        self, image_data: bytes, profile: str = "farm"
    ) -> Optional[DetectionResult]:
        """
        Analyze an image using the specified detection profile.

        Args:
            image_data: The image data as bytes (JPEG format).
            profile: Detection profile ("farm" or "entrance").

        Returns:
            DetectionResult if analysis succeeded, None otherwise.
        """
        prompt = DETECTION_PROMPTS.get(profile, DETECTION_PROMPTS["farm"])

        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            logger.info(f"Analyzing image with '{profile}' profile...")

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
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Parse the response
            response_text = message.content[0].text
            logger.debug(f"Claude response: {response_text}")

            return self._parse_response(response_text, profile)

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return None

    def _parse_response(self, response_text: str, profile: str) -> DetectionResult:
        """
        Parse the structured response from Claude.

        Args:
            response_text: The raw response text from Claude.
            profile: The detection profile used.

        Returns:
            A DetectionResult object.
        """
        lines = response_text.strip().split("\n")

        animals_detected = False
        vehicles_detected = False
        people_detected = False
        people_count = 0
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
            elif line.startswith("PEOPLE_DETECTED:"):
                value = line.split(":", 1)[1].strip().upper()
                people_detected = value == "YES"
            elif line.startswith("PEOPLE_COUNT:"):
                try:
                    people_count = int(line.split(":", 1)[1].strip())
                except ValueError:
                    people_count = 0
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
            people_detected=people_detected,
            description=description or "No description available",
            animal_types=animal_types,
            vehicle_types=vehicle_types,
            people_count=people_count,
            confidence=confidence,
            details=details or "No additional details",
            profile=profile,
        )


def format_detection_message(result: DetectionResult, camera_name: str) -> str:
    """
    Format a detection result as a human-readable message.

    Args:
        result: The detection result to format.
        camera_name: The name of the camera that captured the image.

    Returns:
        A formatted message string.
    """
    has_detection = (
        result.animals_detected or result.vehicles_detected or result.people_detected
    )

    if not has_detection:
        return f"[{camera_name}] No activity detected in the image."

    parts = []

    if result.people_detected:
        people_str = f"{result.people_count} person(s)" if result.people_count else "People"
        parts.append(f"*People Spotted:* {people_str}")

    if result.animals_detected:
        animal_list = ", ".join(result.animal_types) if result.animal_types else "Unknown"
        parts.append(f"*Animals Spotted:* {animal_list}")

    if result.vehicles_detected:
        vehicle_list = ", ".join(result.vehicle_types) if result.vehicle_types else "Unknown"
        parts.append(f"*Vehicles Spotted:* {vehicle_list}")

    # Determine alert type and emoji based on what was detected
    detection_types = []
    if result.people_detected:
        detection_types.append("Person")
    if result.animals_detected:
        detection_types.append("Animal")
    if result.vehicles_detected:
        detection_types.append("Vehicle")

    detection_str = " & ".join(detection_types)

    # Choose emoji based on profile and detection
    if result.profile == "entrance":
        if result.people_detected:
            emoji = "🚶"
        elif result.vehicles_detected:
            emoji = "🚗"
        else:
            emoji = "📷"
    else:  # farm profile
        if result.animals_detected:
            emoji = "🚨"
        elif result.vehicles_detected:
            emoji = "🚗"
        else:
            emoji = "📷"

    header = f"{emoji} *{detection_str} Detected - {camera_name}*"
    spotted_info = "\n".join(parts)

    message = f"""{header}

{spotted_info}
*Confidence:* {result.confidence.capitalize()}

*Description:* {result.description}

*Details:* {result.details}"""

    return message


def should_alert(result: DetectionResult, profile: str) -> bool:
    """
    Determine if an alert should be sent based on the detection result and profile.

    Args:
        result: The detection result.
        profile: The detection profile.

    Returns:
        True if an alert should be sent, False otherwise.
    """
    if profile == "farm":
        # Farm profile: alert on animals or vehicles
        return result.animals_detected or result.vehicles_detected
    elif profile == "entrance":
        # Entrance profile: alert on people, vehicles, or animals
        return result.people_detected or result.vehicles_detected or result.animals_detected
    else:
        # Default: alert on anything
        return (
            result.animals_detected or result.vehicles_detected or result.people_detected
        )
