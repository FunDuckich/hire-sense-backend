import os
import asyncio
import grpc
import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc
from app.core.config import settings
import yandexcloud
import yandex.cloud.ai.stt.v2.stt_service_pb2_grpc as stt_service_grpc

from dotenv import load_dotenv
load_dotenv()

sdk = yandexcloud.SDK(service_account_key={
    "id": settings.YC_API_KEY_ID,
    "private_key": settings.YC_API_KEY_SECRET.replace('\\n', '\n')
})
stt_channel = sdk.client(stt_service_grpc.SttServiceStub)

API_KEY = os.getenv("YC_API_KEY")

# --- ИСПРАВЛЕННАЯ КОНФИГУРАЦИЯ СЕССИИ ---
SESSION_OPTIONS = stt_pb2.StreamingOptions(
    recognition_model=stt_pb2.RecognitionModelOptions(
        audio_format=stt_pb2.AudioFormatOptions(
            container_audio=stt_pb2.ContainerAudio(
                container_audio_type=stt_pb2.ContainerAudio.ContainerAudioType.OGG_OPUS
            )
        ),
        text_normalization=stt_pb2.TextNormalizationOptions(
            text_normalization=stt_pb2.TextNormalizationOptions.TextNormalization.TEXT_NORMALIZATION_ENABLED,
            profanity_filter=True,
            literature_text=False
        ),
        language_restriction=stt_pb2.LanguageRestrictionOptions(
            restriction_type=stt_pb2.LanguageRestrictionOptions.LanguageRestrictionType.WHITELIST,
            language_code=['ru-RU']
        ),
        audio_processing_type=stt_pb2.RecognitionModelOptions.AudioProcessingType.REAL_TIME
    )
)


# ---------------------------------------------


async def generate_requests(audio_stream):
    """
    Генератор, который сначала отправляет сообщение с конфигурацией,
    а затем отправляет аудио-чанки из потока.
    """
    yield stt_pb2.StreamingRequest(session_options=SESSION_OPTIONS)

    async for chunk in audio_stream:
        yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk))


async def recognize(audio_stream):
    """
    Основная функция, которая устанавливает соединение с Yandex SpeechKit,
    отправляет аудиопоток и асинхронно возвращает результаты распознавания.
    """
    credentials = grpc.ssl_channel_credentials()
    async with grpc.aio.secure_channel("stt.api.cloud.yandex.net:443", credentials) as channel:
        stub = stt_service_pb2_grpc.RecognizerStub(channel)

        metadata = [("authorization", f"Api-Key {API_KEY}")]

        stream = stub.RecognizeStreaming(generate_requests(audio_stream), metadata=metadata)

        try:
            async for response in stream:
                event_type = response.WhichOneof('Event')

                # --- ИСПРАВЛЕННЫЙ БЛОК С ПРОВЕРКОЙ ---
                if event_type == 'partial' and len(response.partial.alternatives) > 0:
                    yield {"type": "partial", "text": response.partial.alternatives[0].text}

                elif event_type == 'final' and len(response.final.alternatives) > 0:
                    yield {"type": "final", "text": response.final.alternatives[0].text}

                elif event_type == 'final_refinement' and len(
                        response.final_refinement.normalized_text.alternatives) > 0:
                    yield {"type": "final_refinement",
                           "text": response.final_refinement.normalized_text.alternatives[0].text}
                # ----------------------------------------

        except asyncio.CancelledError:
            print("Распознавание прервано клиентом.")
        except grpc.aio.AioRpcError as e:
            print(f"Ошибка gRPC: {e.details()}")
            yield {"type": "error", "text": f"Ошибка сервера распознавания: {e.details()}"}