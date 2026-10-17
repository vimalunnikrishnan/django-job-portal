import os
import time

from django.conf import settings
from .base import AIRateLimitError
from .mock_provider import MockAIProvider

class AIBridgeService:

    def __init__(self, provider=None, max_retries=3):
        if provider is not None:
            self.provider = provider
        elif settings.AI_PROVIDER == "mock":
            self.provider = MockAIProvider()
        else:
            raise ValueError(
                f"Unsupported AI_PROVIDER: {settings.AI_PROVIDER}"
            )
        self.max_retries = max_retries
        self.api_key = os.getenv("AI_API_KEY")

    def _execute(self, operation, *args, **kwargs):
        last_error = None

        for attempt in range(self.max_retries):
            try:
                result = operation(*args, **kwargs)

                if result.get("success"):
                    return result

                last_error = result.get(
                    "error",
                    "AI provider operation failed.",
                )

            except AIRateLimitError:
                last_error = "AI provider rate limit exceeded."

            except Exception as exc:
                last_error = str(exc)

            if attempt < self.max_retries - 1:
                time.sleep(0.1 * (attempt + 1))

        return {
            "success": False,
            "error": last_error or "AI provider operation failed.",
        }

    def generate_text(self, prompt):
        return self._execute(
            self.provider.generate_text,
            prompt,
        )

    def speech_to_text(self, audio_data):
        return self._execute(
            self.provider.speech_to_text,
            audio_data,
        )

    def text_to_speech(self, text, voice="default", language="en"):
        return self._execute(
            self.provider.text_to_speech,
            text,
            voice,
            language,
        )

    def make_call(
        self,
        phone_number,
        voice="default",
        language="en",
    ):
        return self._execute(
            self.provider.make_call,
            phone_number,
            voice,
            language,
        )