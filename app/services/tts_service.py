import requests
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.llm_service import get_iam_token

TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"


def synthesize_speech(text: str, voice: str = "alexander", speed: float = 1.0) -> bytes | None:
    """
    Синтезирует речь из текста с помощью Yandex SpeechKit REST API v3.

    :param text: Текст для синтеза.
    :param voice: Голос (например, 'alexander', 'alena', 'filipp', 'oksana_sad').
    :param speed: Скорость речи (от 0.1 до 3.0).
    :return: Аудиоданные в формате OggOpus или None в случае ошибки.
    """
    if not text:
        return None

    iam_token = get_iam_token()

    headers = {
        'Authorization': f'Bearer {iam_token}',
    }

    data = {
        'text': text,
        'lang': 'ru-RU',
        'voice': voice,
        'folderId': settings.YC_FOLDER_ID,
        'format': 'oggopus',
        'speed': str(speed)
    }

    try:
        response = requests.post(TTS_URL, headers=headers, data=data)

        response.raise_for_status()

        return response.content

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при вызове TTS API: {http_err}")
        print(f"Тело ответа: {http_err.response.text}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text-to-Speech service failed."
        ) from http_err
    except Exception as e:
        print(f"Неизвестная ошибка в TTS сервисе: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred in the TTS service."
        ) from e