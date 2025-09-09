import asyncio
import grpc
import inspect
import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc
from app.services.llm_service import get_iam_token


def get_stt_stub():
    cred = grpc.ssl_channel_credentials()
    channel = grpc.aio.secure_channel('stt.api.cloud.yandex.net:443', cred)
    return stt_service_pb2_grpc.RecognizerStub(channel)


SESSION_OPTIONS = stt_pb2.StreamingOptions(
    recognition_model=stt_pb2.RecognitionModelOptions(
        model='general',
        audio_format=stt_pb2.AudioFormatOptions(
            raw_audio=stt_pb2.RawAudio(
                audio_encoding=stt_pb2.RawAudio.AudioEncoding.LINEAR16_PCM,
                sample_rate_hertz=48000
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


class StreamRecognizer:
    def __init__(self):
        self._cred = grpc.ssl_channel_credentials()
        self._channel = grpc.aio.secure_channel('stt.api.cloud.yandex.net:443', self._cred)
        self._stub = stt_service_pb2_grpc.RecognizerStub(self._channel)
        self._iam_token = None
        self._metadata = None

    async def recognize(self, audio_stream_generator):
        iam = get_iam_token()
        if inspect.isawaitable(iam):
            self._iam_token = await iam
        else:
            self._iam_token = iam
        self._metadata = [('authorization', f'Bearer {self._iam_token}')]

        async def generate_requests():
            yield stt_pb2.StreamingRequest(session_options=SESSION_OPTIONS)
            has_sent_audio = False
            async for chunk in audio_stream_generator:
                if chunk is None:
                    break
                has_sent_audio = True
                yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=chunk))
            if has_sent_audio:
                yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=b''))

        try:
            responses = self._stub.RecognizeStreaming(generate_requests(), metadata=self._metadata)
            async for response in responses:
                event_type = response.WhichOneof('Event')
                if event_type == 'partial' and len(response.partial.alternatives) > 0:
                    yield {"type": "partial", "text": response.partial.alternatives[0].text}
                elif event_type == 'final' and len(response.final.alternatives) > 0:
                    yield {"type": "final", "text": response.final.alternatives[0].text}
                elif event_type == 'final_refinement' and len(
                        response.final_refinement.normalized_text.alternatives) > 0:
                    yield {"type": "final_refinement",
                           "text": response.final_refinement.normalized_text.alternatives[0].text}
        except asyncio.CancelledError:
            return
        except grpc.aio.AioRpcError as e:
            yield {"type": "error", "text": f"Ошибка сервера распознавания: {e.details()}"}

    async def close(self):
        await self._channel.close()
