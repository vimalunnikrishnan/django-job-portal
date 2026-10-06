from abc import ABC, abstractmethod

class AIRateLimitError(Exception):
    """Raised when an AI provider rate limit is exceeded."""
    

class AIProvider(ABC):

    @abstractmethod
    def generate_text(self, prompt):
        pass

    @abstractmethod
    def speech_to_text(self, audio_data):
        pass

    @abstractmethod
    def text_to_speech(self, text, voice, language):
        pass

    @abstractmethod
    def make_call(self, phone_number, voice, language):
        pass