import io
import grpc
import pydub
from app.services.llm_service import get_iam_token
import yandex.cloud.ai.tts.v3.tts_pb2 as tts_pb2
import yandex.cloud.ai.tts.v3.tts_service_pb2_grpc as tts_service_pb2_grpc


def synthesize_speech(text: str) -> bytes | None:
    iam_token = get_iam_token()
    if not iam_token or not text:
        return None

    request = tts_pb2.UtteranceSynthesisRequest(
        text=text,
        output_audio_spec=tts_pb2.AudioFormatOptions(
            container_audio=tts_pb2.ContainerAudio(
                container_audio_type=tts_pb2.ContainerAudio.OGG_OPUS
            )
        ),
        hints=[
            tts_pb2.Hints(voice='masha'),
            tts_pb2.Hints(role='friendly'),
            tts_pb2.Hints(speed=1.1),
        ],
        loudness_normalization_type=tts_pb2.UtteranceSynthesisRequest.LUFS
    )

    try:
        cred = grpc.ssl_channel_credentials()
        with grpc.secure_channel('tts.api.cloud.yandex.net:443', cred) as channel:
            stub = tts_service_pb2_grpc.SynthesizerStub(channel)
            metadata = (('authorization', f'Bearer {iam_token}'),)

            iterator = stub.UtteranceSynthesis(request, metadata=metadata)

            audio_chunks = []
            for response in iterator:
                audio_chunks.append(response.audio_chunk.data)

            return b"".join(audio_chunks)

    except grpc.RpcError as err:
        print(f'TTS gRPC Error: code {err.code()}, message: {err.details()}')
        return None