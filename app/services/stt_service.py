import asyncio
import grpc
import json
import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc
from app.core.config import settings
import yandexcloud

try:
    with open("authorized_key.json", 'r', encoding='utf-8') as key_file:
        sa_key_data = json.load(key_file)
except Exception as e:
    raise RuntimeError(f"Не удалось прочитать файл authorized_key.json: {e}")

sdk = yandexcloud.SDK(service_account_key=sa_key_data)

recognizer_stub = sdk.client(stt_service_pb2_grpc.RecognizerStub)

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


async def generate_requests(audio_stream):
    yield stt_pb2.StreamingRequest(session_options=SESSION_OPTIONS)

    async for chunk in audio_stream:
        yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk))


async def recognize_stream(audio_stream):
    request_generator = generate_requests(audio_stream)
    responses = recognizer_stub.RecognizeStreaming(request_generator)

    try:
        async for response in responses:
            event_type = response.WhichOneof('Event')

            if event_type == 'partial' and len(response.partial.alternatives) > 0:
                yield {"type": "partial", "text": response.partial.alternatives[0].text}

            elif event_type == 'final' and len(response.final.alternatives) > 0:
                yield {"type": "final", "text": response.final.alternatives[0].text}

            elif event_type == 'final_refinement' and len(response.final_refinement.normalized_text.alternatives) > 0:
                yield {"type": "final_refinement",
                       "text": response.final_refinement.normalized_text.alternatives[0].text}

    except asyncio.CancelledError:
        print("Распознавание прервано.")
    except grpc.aio.AioRpcError as e:
        print(f"Ошибка gRPC в STT сервисе: {e.details()}")
        yield {"type": "error", "text": f"Ошибка сервера распознавания: {e.details()}"}
