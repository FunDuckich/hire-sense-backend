import asyncio
import grpc
import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc
from app.services.llm_service import get_iam_token


def get_stt_stub():
    cred = grpc.ssl_channel_credentials()
    channel = grpc.aio.secure_channel('stt.api.cloud.yandex.net:443', cred)
    return stt_service_pb2_grpc.RecognizerStub(channel)


SESSION_OPTIONS = stt_pb2.StreamingOptions(
    recognition_model=stt_pb2.RecognitionModelOptions(
        audio_format=stt_pb2.AudioFormatOptions(
            container_audio=stt_pb2.ContainerAudio(
                container_audio_type=stt_pb2.ContainerAudio.ContainerAudioType.OGG_OPUS
            )
        ),
        text_normalization=stt_pb2.TextNormalizationOptions(
            text_normalization=stt_pb2.TextNormalizationOptions.TextNormalization.TEXT_NORMALIZATION_ENABLED,
            profanity_filter=False,
            literature_text=True
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

    has_sent_audio = False
    async for chunk in audio_stream:
        yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk))
        has_sent_audio = True

    if has_sent_audio:
        yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=b''))


async def recognize_stream(audio_stream):
    cred = grpc.ssl_channel_credentials()
    channel = grpc.aio.secure_channel('stt.api.cloud.yandex.net:443', cred)
    recognizer_stub = stt_service_pb2_grpc.RecognizerStub(channel)

    iam_token = get_iam_token()
    metadata = [('authorization', f'Bearer {iam_token}')]

    request_generator = generate_requests(audio_stream)
    responses = recognizer_stub.RecognizeStreaming(request_generator, metadata=metadata)

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
    finally:
        await channel.close()
