from abc import ABC, abstractmethod
import os
from app.core.config import settings


class AudioStorageService(ABC):

    @abstractmethod
    def save(self, session_id: int, audio_bytes: bytes) -> str:
        pass

    @abstractmethod
    def get(self, file_id: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        pass


class LocalStorageService(AudioStorageService):

    def __init__(self):
        os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)
        self.storage_path = settings.LOCAL_STORAGE_PATH

    def _get_filepath(self, session_id: int) -> str:
        return os.path.join(self.storage_path, f"session_{session_id}.ogg")

    def save(self, session_id: int, audio_bytes: bytes) -> str:
        filepath = self._get_filepath(session_id)
        try:
            with open(filepath, "wb") as f:
                f.write(audio_bytes)
            print(f"Аудио для сессии {session_id} сохранено в {filepath}")
            return filepath
        except IOError as e:
            print(f"Ошибка сохранения файла для сессии {session_id}: {e}")
            raise

    def get(self, file_id: str) -> bytes:
        try:
            with open(file_id, "rb") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Файл не найден: {file_id}")
            raise
        except IOError as e:
            print(f"Ошибка чтения файла {file_id}: {e}")
            raise

    def delete(self, file_id: str) -> bool:
        try:
            os.remove(file_id)
            print(f"Файл {file_id} успешно удален.")
            return True
        except FileNotFoundError:
            print(f"Файл {file_id} не найден для удаления (возможно, уже удален).")
            return True
        except OSError as e:
            print(f"Ошибка удаления файла {file_id}: {e}")
            return False
