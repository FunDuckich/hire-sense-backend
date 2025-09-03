from abc import ABC, abstractmethod


class SpeechAnalyticsService(ABC):
    @abstractmethod
    async def analyze_audio(self, audio_file_path: str,
                            custom_vocabularies: dict[str, list[str]] | None = None) -> dict:
        pass
