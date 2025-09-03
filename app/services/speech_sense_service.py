import asyncio
import json
import yandexcloud
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2 as analysis_service_pb2
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2_grpc as analysis_service_pb2_grpc
from app.core.config import settings
from app.services.speech_analytics_service import SpeechAnalyticsService  ### ИЗМЕНЕНИЕ: Импортируем твою абстракцию

UNIVERSAL_VOCABULARIES = {
    "inconfidence": ["наверное", "возможно", "я думаю", "вроде бы", "не уверен", "сложно сказать", "насколько я помню"],
    "negativity": ["ужасный", "токсичный", "конфликт", "не платили", "заставляли", "ненавидел", "глупый менеджер"],
    "achievements": ["реализовал", "внедрил", "оптимизировал", "увеличил", "сократил", "разработал с нуля", "руководил",
                     "достиг"]
}


class SpeechSenseService(SpeechAnalyticsService):
    def __init__(self):
        sdk = yandexcloud.SDK(service_account_key=self._get_sa_key())
        self.analysis_stub = sdk.client(analysis_service_pb2_grpc.AnalysisServiceStub)
        self.max_wait_time_seconds = 300
        self.check_interval_seconds = 10

    def _get_sa_key(self) -> dict:
        try:
            with open(settings.YC_SA_KEY_FILE_PATH, 'r', encoding='utf-8') as key_file:
                return json.load(key_file)
        except Exception as e:
            raise RuntimeError(
                f"Не удалось прочитать файл сервисного ключа по пути '{settings.YC_SA_KEY_FILE_PATH}': {e}")

    async def _start_analysis(self, audio_file_path: str, vocabularies_to_use: dict) -> str:
        print(f"Запуск анализа SpeechSense для файла: {audio_file_path}")
        print(f"Используемые словари: {list(vocabularies_to_use.keys())}")
        operation_id = "some_operation_id_from_sdk"  # Заглушка
        if not operation_id:
            raise RuntimeError("API SpeechSense не вернул ID операции.")
        return operation_id

    async def _check_analysis_status(self, operation_id: str) -> dict | None:
        is_done = True
        if is_done:
            analysis_result = {"some": "result"}
            return analysis_result
        return None

    async def analyze_audio(self, audio_file_path: str,
                            custom_vocabularies: dict[str, list[str]] | None = None) -> dict:
        all_vocabularies = UNIVERSAL_VOCABULARIES.copy()
        if custom_vocabularies:
            all_vocabularies.update(custom_vocabularies)

        operation_id = await self._start_analysis(audio_file_path, all_vocabularies)

        elapsed_time = 0
        while elapsed_time < self.max_wait_time_seconds:
            result = await self._check_analysis_status(operation_id)
            if result:
                print(f"Анализ SpeechSense для операции {operation_id} успешно завершен.")
                return result

            await asyncio.sleep(self.check_interval_seconds)
            elapsed_time += self.check_interval_seconds

        raise TimeoutError(f"Тайм-аут ожидания анализа SpeechSense для операции {operation_id}.")


speech_sense_service = SpeechSenseService()
