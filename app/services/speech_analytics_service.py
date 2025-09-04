from abc import ABC, abstractmethod

class SpeechAnalyticsService(ABC):
    @abstractmethod
    async def analyze_audio(self, audio_file_path: str) -> dict:
        pass