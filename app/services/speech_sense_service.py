import asyncio
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2 as analysis_service_pb2
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2_grpc as analysis_service_pb2_grpc
import yandexcloud
from app.core.config import settings

inconfidence = ["наверное", "возможно", "я думаю", "вроде бы", "не уверен", "сложно сказать", "насколько я помню"]
negativity = ["ужасный", "токсичный", "конфликт", "не платили", "заставляли", "ненавидел", "глупый менеджер"]
achievements = ["реализовал", "внедрил", "оптимизировал", "увеличил", "сократил", "разработал с нуля", "руководил", "достиг"]

# (Здесь может быть код для получения yandexcloud.SDK, похожий на stt_service)

class SpeechSenseService:
    def __init__(self):
        # Инициализация SDK и gRPC-стаба
        sdk = yandexcloud.SDK(service_account_key=self._get_sa_key())
        self.analysis_stub = sdk.client(analysis_service_pb2_grpc.AnalysisServiceStub)

    def _get_sa_key(self) -> dict:
        # Вспомогательный метод для загрузки ключа
        import json
        try:
            with open(settings.YC_SA_KEY_FILE_PATH, 'r', encoding='utf-8') as key_file:
                return json.load(key_file)
        except Exception as e:
            raise RuntimeError(f"Не удалось прочитать файл ключа: {e}")

    async def upload_audio_and_start_analysis(self, file_path: str) -> str | None:
        """
        Загружает локальный аудиофайл в SpeechSense и запускает асинхронную операцию анализа.
        Возвращает ID операции.
        """
        # Здесь будет gRPC-запрос на загрузку файла и запуск анализа
        # Это асинхронная операция (long-running operation)
        print(f"Запуск анализа SpeechSense для файла: {file_path}")
        # ... код для yandex.cloud.ai.speechsense.v1.analysis_service_pb2.UploadAudioRequest
        # Возвращает operation.id
        operation_id = "some_operation_id_from_sdk" # Заглушка
        return operation_id

    async def check_analysis_status(self, operation_id: str) -> dict | None:
        """
        Проверяет статус операции анализа и, если она завершена, возвращает результат.
        """
        # Здесь будет gRPC-запрос на проверку статуса long-running operation
        print(f"Проверка статуса операции SpeechSense: {operation_id}")
        # ... код для проверки статуса операции
        # Если операция завершена (done=True), извлекаем результат
        analysis_result = {"some": "result"} # Заглушка
        return analysis_result

    async def analyze_audio_file(self, file_path: str) -> dict | None:
        """
        Полный цикл анализа: загружает файл, ждет завершения и возвращает результат.
        """
        operation_id = await self.upload_audio_and_start_analysis(file_path)
        if not operation_id:
            print("Не удалось запустить операцию анализа в SpeechSense.")
            return None

        # Цикл опроса статуса
        max_wait_time_seconds = 300  # 5 минут
        check_interval_seconds = 10
        elapsed_time = 0

        while elapsed_time < max_wait_time_seconds:
            result = await self.check_analysis_status(operation_id)
            if result:  # Если результат не None, значит, анализ завершен
                print("Анализ SpeechSense успешно завершен.")
                return result

            print(f"Анализ еще не готов, ожидание {check_interval_seconds} сек...")
            await asyncio.sleep(check_interval_seconds)
            elapsed_time += check_interval_seconds

        print(f"Тайм-аут ожидания анализа SpeechSense для операции {operation_id}.")
        return None

speech_sense_service = SpeechSenseService()