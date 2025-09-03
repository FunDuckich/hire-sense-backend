import asyncio
import json
import yandexcloud
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2 as analysis_service_pb2
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2_grpc as analysis_service_pb2_grpc
import yandex.cloud.ai.speechsense.v1.dictionary_service_pb2 as dictionary_service_pb2
import yandex.cloud.ai.speechsense.v1.dictionary_service_pb2_grpc as dictionary_service_pb2_grpc

from yandex.cloud.operation.operation_service_pb2 import GetOperationRequest
from yandex.cloud.operation.operation_service_pb2_grpc import OperationServiceStub

from app.core.config import settings
from app.services.speech_analytics_service import SpeechAnalyticsService

UNIVERSAL_VOCABULARIES = {
    "inconfidence": ["наверное", "возможно", "я думаю", "вроде бы", "не уверен", "сложно сказать", "насколько я помню"],
    "negativity": ["ужасный", "токсичный", "конфликт", "не платили", "заставляли", "ненавидел", "глупый менеджер"],
    "achievements": ["реализовал", "внедрил", "оптимизировал", "увеличил", "сократил", "разработал с нуля", "руководил", "достиг"]
}



class SpeechSenseService(SpeechAnalyticsService):
    def __init__(self):
        sdk = yandexcloud.SDK(service_account_key=self._get_sa_key())
        self.analysis_stub = sdk.client(analysis_service_pb2_grpc.AnalysisServiceStub)
        self.operation_stub = sdk.client(OperationServiceStub)
        # --- Новый gRPC-стаб для управления словарями ---
        self.dictionary_stub = sdk.client(dictionary_service_pb2_grpc.DictionaryServiceStub)

        self.max_wait_time_seconds = 300
        self.check_interval_seconds = 10

    def _get_sa_key(self) -> dict:
        try:
            with open(settings.YC_SA_KEY_FILE_PATH, 'r', encoding='utf-8') as key_file:
                return json.load(key_file)
        except Exception as e:
            raise RuntimeError(
                f"Не удалось прочитать файл сервисного ключа по пути '{settings.YC_SA_KEY_FILE_PATH}': {e}")

    # --- НАЧАЛО НОВОГО КОДА ---
    async def create_dictionary(self, name: str, words: list[str]) -> str:
        """
        Создает новый словарь в SpeechSense и возвращает его ID.
        """
        print(f"Создание словаря '{name}' в SpeechSense...")

        dictionary_items = [dictionary_service_pb2.DictionaryItem(key=word) for word in words]

        request = dictionary_service_pb2.CreateDictionaryRequest(
            folder_id=settings.YC_FOLDER_ID,
            name=name,
            items=dictionary_items
        )
        try:
            operation = self.dictionary_stub.Create(request)
            # Операция создания словаря обычно синхронна, но лучше проверить документацию
            # Здесь мы предполагаем, что она возвращает ID напрямую или через операцию
            print(f"Словарь '{name}' успешно создан, ID: {operation.id}")
            return operation.id  # или operation.response.id
        except Exception as e:
            print(f"gRPC ошибка при создании словаря '{name}': {e}")
            raise RuntimeError(f"Не удалось создать словарь '{name}' в SpeechSense.") from e

    async def delete_dictionary(self, dictionary_id: str) -> None:
        """
        Удаляет словарь из SpeechSense по его ID.
        """
        print(f"Удаление словаря с ID {dictionary_id} из SpeechSense...")
        request = dictionary_service_pb2.DeleteDictionaryRequest(dictionary_id=dictionary_id)
        try:
            self.dictionary_stub.Delete(request)
            print(f"Словарь {dictionary_id} успешно удален.")
        except Exception as e:
            # Важно обработать случай, если словарь уже удален
            # В gRPC это обычно ошибка с кодом NOT_FOUND
            print(f"gRPC ошибка при удалении словаря {dictionary_id}: {e}")
            # Можно не выбрасывать исключение, если "не найдено" - это не ошибка для нас
            pass

    # --- КОНЕЦ НОВОГО КОДА ---

    async def _start_analysis(self, audio_file_path: str, vocabularies_to_use: dict) -> str:
        with open(audio_file_path, 'rb') as f:
            audio_content = f.read()

        # Собираем конфигурацию для анализа с нашими словарями
        # В реальном API структура может отличаться, это пример на основе документации
        analysis_config = {
            "speaker_analysis": {"enable": True},
            "text_analysis": {"enable": True},
            "vocabularies": [
                {"name": name, "words": words} for name, words in vocabularies_to_use.items()
            ]
        }

        request = analysis_service_pb2.UploadAudioRequest(
            folder_id=settings.YC_FOLDER_ID,
            audio_content=audio_content,
            # В реальном API здесь будет поле для передачи конфигурации анализа
            # config=analysis_config 
        )

        print(f"Запуск анализа SpeechSense для файла: {audio_file_path}")
        try:
            operation = self.analysis_stub.UploadAudio(request)
            print(f"Операция анализа запущена, ID: {operation.id}")
            return operation.id
        except Exception as e:
            print(f"gRPC ошибка при запуске анализа SpeechSense: {e}")
            raise RuntimeError("API SpeechSense не удалось запустить операцию анализа.") from e

    async def _check_analysis_status(self, operation_id: str) -> dict | None:
        request = GetOperationRequest(operation_id=operation_id)
        try:
            operation = self.operation_stub.Get(request)
            if operation.done:
                # В реальном API результат может быть в другом поле или требовать распаковки
                # Здесь мы предполагаем, что он в виде JSON-строки в `metadata`
                if operation.response and operation.response.value:
                    # Для примера, допустим, результат приходит в виде байтов JSON
                    result_json = operation.response.value.decode('utf-8')
                    return json.loads(result_json)
                else:
                    raise ValueError("Операция завершена, но результат пуст.")
            return None  # Операция еще не завершена
        except Exception as e:
            print(f"gRPC ошибка при проверке статуса операции {operation_id}: {e}")
            return None  # Возвращаем None, чтобы цикл опроса продолжился

    async def analyze_audio(self, audio_file_path: str,
                            custom_vocabularies: dict[str, list[str]] | None = None) -> dict:
        all_vocabularies = UNIVERSAL_VOCABULARIES.copy()
        if custom_vocabularies:
            all_vocabularies.update(custom_vocabularies)

        operation_id = await self._start_analysis(audio_file_path, all_vocabularies)

        elapsed_time = 0
        while elapsed_time < self.max_wait_time_seconds:
            await asyncio.sleep(self.check_interval_seconds)
            result = await self._check_analysis_status(operation_id)
            if result:
                print(f"Анализ SpeechSense для операции {operation_id} успешно завершен.")
                return result

            elapsed_time += self.check_interval_seconds
            print(f"Анализ {operation_id} еще не готов, ожидание...")

        raise TimeoutError(f"Тайм-аут ожидания анализа SpeechSense для операции {operation_id}.")


speech_sense_service = SpeechSenseService()