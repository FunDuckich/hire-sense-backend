import asyncio
import json
from google.protobuf.json_format import MessageToDict
import yandexcloud
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2 as analysis_service_pb2
import yandex.cloud.ai.speechsense.v1.analysis_service_pb2_grpc as analysis_service_pb2_grpc
from yandex.cloud.operation.operation_service_pb2 import GetOperationRequest
from yandex.cloud.operation.operation_service_pb2_grpc import OperationServiceStub

from app.core.config import settings
from app.services.speech_analytics_service import SpeechAnalyticsService


class SpeechSenseService(SpeechAnalyticsService):
    def __init__(self):
        try:
            self.sdk = yandexcloud.SDK(service_account_key=self._get_sa_key())
            self.analysis_stub = self.sdk.client(analysis_service_pb2_grpc.AnalysisServiceStub)
            self.operation_stub = self.sdk.client(OperationServiceStub)
        except Exception as e:
            # Предотвращаем падение приложения при старте, если ключ не настроен
            print(f"ОШИБКА: Не удалось инициализировать SpeechSenseService: {e}")
            self.sdk = None
            self.analysis_stub = None
            self.operation_stub = None

        self.max_wait_time_seconds = 300
        self.check_interval_seconds = 10

    def _get_sa_key(self) -> dict:
        try:
            with open(settings.YC_SA_KEY_FILE_PATH, 'r', encoding='utf-8') as key_file:
                return json.load(key_file)
        except Exception as e:
            raise RuntimeError(
                f"Не удалось прочитать файл сервисного ключа по пути '{settings.YC_SA_KEY_FILE_PATH}': {e}")

    async def _start_analysis(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as f:
            audio_content = f.read()

        request = analysis_service_pb2.UploadAudioRequest(
            connection_id=settings.YC_SPEECHSENSE_CONNECTION_ID,
            audio_content=audio_content
        )

        try:
            operation = await self.analysis_stub.UploadAudio(request)
            if not operation or not operation.id:
                raise RuntimeError("API SpeechSense не вернул ID операции.")
            return operation.id
        except Exception as e:
            print(f"Ошибка gRPC при запуске анализа SpeechSense: {e}")
            raise RuntimeError("Не удалось запустить операцию анализа в SpeechSense.")

    async def _check_analysis_status(self, operation_id: str) -> dict | None:
        request = GetOperationRequest(operation_id=operation_id)
        try:
            operation = await self.operation_stub.Get(request)
        except Exception as e:
            print(f"Ошибка gRPC при проверке статуса операции {operation_id}: {e}")
            # Возвращаем None, чтобы цикл опроса продолжился
            return None

        if operation.done:
            # Преобразуем protobuf-ответ в словарь для удобства работы
            unpacked_response = analysis_service_pb2.UploadAudioResponse()
            operation.response.Unpack(unpacked_response)
            return MessageToDict(unpacked_response)

        return None

    async def analyze_audio(self, audio_file_path: str) -> dict:
        if not self.analysis_stub or not self.operation_stub:
            raise ConnectionError("SpeechSenseService не был инициализирован. Проверьте конфигурацию.")

        operation_id = await self._start_analysis(audio_file_path)

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