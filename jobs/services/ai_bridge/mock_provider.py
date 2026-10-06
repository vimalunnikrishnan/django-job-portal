from .base import AIProvider


class MockAIProvider(AIProvider):

    def generate_text(self, prompt):
        return {
            "success": True,
            "text": f"Mock AI response for: {prompt}",
        }

    def speech_to_text(self, audio_data):
        return {
            "success": True,
            "text": "Mock speech-to-text transcript.",
        }

    def text_to_speech(self, text, voice, language):
        return {
            "success": True,
            "voice": voice,
            "language": language,
            "text": text,
        }

    def make_call(self, phone_number, voice, language):
        return {
            "success": True,
            "call_id": "MOCK-CALL-001",
            "phone_number": phone_number,
            "voice": voice,
            "language": language,
            "status": "QUEUED",
        }