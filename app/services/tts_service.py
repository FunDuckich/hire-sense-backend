import requests
from app.core.config import settings
from app.services.llm_service import get_iam_token


def synthesize_speech(text: str) -> bytes | None:
    """
    Синтезирует речь из текста с помощью Yandex SpeechKit REST API v3.
    Использует единый механизм получения IAM-токена.
    """
    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

    try:
        iam_token = get_iam_token()
    except Exception as e:
        print(f"Ошибка получения IAM-токена в TTS сервисе: {e}")
        return None

    headers = {
        'Authorization': f'Bearer {iam_token}',
    }

    data = {
        'text': text,
        'lang': 'ru-RU',
        'folderId': settings.YC_FOLDER_ID,
        'voice': 'alena',
        'emotion': 'good',
        'speed': '1.0',
        'format': 'oggopus'
    }

    try:
        print(f"Отправка запроса на синтез речи для текста: '{text[:30]}...'")
        response = requests.post(url, headers=headers, data=data, stream=False)
        response.raise_for_status()  # Вызовет исключение для статусов 4xx/5xx

        return response.content

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при синтезе речи: {http_err}")
        print(f"Тело ответа: {http_err.response.text}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при синтезе речи: {e}")
        return None