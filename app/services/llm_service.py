import time
import json
from datetime import datetime

import requests
import jwt
from typing import TypedDict
from app.core.config import settings


class IamTokenCache(TypedDict):
    token: str | None
    expires_at: int


_iam_token_cache: IamTokenCache = {
    "token": None,
    "expires_at": 0
}


def get_iam_token() -> str:
    """Получает IAM-токен, кеширует его и обновляет при необходимости."""
    now_ts = int(time.time())
    if _iam_token_cache["token"] is None or _iam_token_cache["expires_at"] <= now_ts + 60:
        print("Обновление IAM-токена...")
        try:
            with open("authorized_key.json", 'r', encoding='utf-8') as key_file:
                private_key_data = json.load(key_file)
                private_key = private_key_data["private_key"]

            now_jwt = int(time.time())
            payload = {
                'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                'iss': settings.YC_SERVICE_ACCOUNT_ID,
                'iat': now_jwt,
                'exp': now_jwt + 3600
            }

            encoded_token = jwt.encode(
                payload,
                private_key,
                algorithm='PS256',
                headers={'kid': settings.YC_KEY_ID}
            )

            response = requests.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={'jwt': encoded_token}
            )
            response.raise_for_status()
            result = response.json()

            iam_token = result.get("iamToken")
            expires_at_str = result.get("expiresAt")

            if not iam_token or not expires_at_str:
                raise ValueError("Invalid response from IAM API")

            # --- ПРАВИЛЬНЫЙ СПОСОБ ПОЛУЧЕНИЯ ВРЕМЕНИ ЖИЗНИ ---
            # Парсим строку времени и переводим в Unix timestamp
            expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            expires_at_ts = int(expires_at_dt.timestamp())

            _iam_token_cache["token"] = iam_token
            _iam_token_cache["expires_at"] = expires_at_ts
            print("IAM-токен успешно обновлен.")

        except Exception as e:
            print(f"Ошибка получения IAM-токена: {e}")
            raise IOError("Could not retrieve IAM token") from e

    token = _iam_token_cache["token"]
    if token is None:
        raise ValueError("Cached IAM token is None")

    return token


def call_yandex_gpt(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str | None:
    iam_token = get_iam_token()

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {iam_token}",
    }

    body = {
        "modelUri": f"gpt://{settings.YC_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": "4000"
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()

        response_json = response.json()

        return response_json['result']['alternatives'][0]['message']['text']

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при вызове YandexGPT: {http_err}")
        print(f"Тело ответа: {http_err.response.text}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при вызове YandexGPT: {e}")
        return None


def analyze_resume(vacancy_details: dict, resume_md: str) -> dict | None:
    system_prompt = (
        "Ты — высокоточный HR-аналитик. Твоя задача — провести объективный скрининг резюме. "
        "Проанализируй предоставленные данные и верни результат. "
        "Твой ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON-объекта. "
        "Не используй разметку Markdown, вводные фразы, объяснения или любые символы до или после JSON-объекта."
    )

    user_prompt = f"""
    Проанализируй резюме кандидата на соответствие требованиям вакансии.
    В `overall_match_score` поставь число от 0 до 100, где 100 - идеальное совпадение.
    В `summary` напиши краткий вывод на 2-3 предложения.
    В `questions_to_ask` сформулируй 3-4 ключевых вопроса, которые нужно задать кандидату на интервью.

    Верни результат в формате JSON со следующей структурой:
    {{
      "overall_match_score": <number>,
      "summary": "<string>",
      "competency_check": [
        {{ "criterion": "<название критерия из вакансии>", "confirmed": <boolean>, "evidence": "<цитата или краткое обоснование из резюме>" }}
      ],
      "questions_to_ask": [
        "<вопрос 1>",
        "<вопрос 2>",
        "<вопрос 3>"
      ],
      "red_flags": ["<список потенциальных проблем, если есть>"]
    }}

    Вот требования вакансии:
    ---
    {json.dumps(vacancy_details, ensure_ascii=False, indent=2)}
    ---

    Вот резюме кандидата:
    ---
    {resume_md}
    ---
    """

    print("Отправка запроса на анализ резюме в YandexGPT...")
    response_text = call_yandex_gpt(system_prompt, user_prompt, temperature=0.4)

    if not response_text:
        return None

    try:
        clean_response = response_text.strip()

        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]

        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]

        return json.loads(clean_response)

    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON из ответа LLM: {e}")
        print(f"Полученный ответ (до очистки): {response_text}")
        return None
