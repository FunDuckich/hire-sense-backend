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
    now_ts = int(time.time())
    if _iam_token_cache["token"] is None or _iam_token_cache["expires_at"] <= now_ts + 60:
        print("Обновление IAM-токена...")
        try:
            with open(settings.YC_SA_KEY_FILE_PATH, 'r', encoding='utf-8') as key_file:
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


def get_interview_response(
        history: list[dict],
        vacancy_details: dict,
        resume_summary: dict
) -> str | None:
    system_prompt = (
        "Ты — HR-аватар по имени Алекс. Твоя задача — провести первичное собеседование на IT-вакансию. "
        "Будь профессионален, вежлив и дружелюбен. Задавай по ОДНОМУ вопросу за раз. "
        "Твоя цель — раскрыть опыт кандидата и его соответствие ключевым требованиям. "
        "Задавай открытые вопросы, которые требуют развернутого ответа. "
        "Если кандидат отвечает коротко, задай уточняющий вопрос по той же теме. "
        "Не повторяй вопросы, которые уже были в диалоге."
    )

    vacancy_context = json.dumps(vacancy_details, ensure_ascii=False, indent=2)
    resume_context = json.dumps(resume_summary, ensure_ascii=False, indent=2)

    user_prompt = f"""
    Вот информация о вакансии:
    --- VACANCY INFO ---
    {vacancy_context}
    --- END VACANCY INFO ---

    Вот краткая выжимка из резюме кандидата и вопросы, которые нужно было уточнить:
    --- RESUME SUMMARY ---
    {resume_context}
    --- END RESUME SUMMARY ---

    Вот текущая история нашего диалога:
    --- DIALOGUE HISTORY ---
    {json.dumps(history, ensure_ascii=False, indent=2)}
    --- END DIALOGUE HISTORY ---

    ЗАДАЧА: На основе всей этой информации сгенерируй СЛЕДУЮЩИЙ ОДИН вопрос или реплику для кандидата.
    Твой ответ должен быть только текстом вопроса. Без лишних слов, вроде "Хорошо, следующий вопрос:".
    """

    print("Отправка запроса на генерацию вопроса для интервью в YandexGPT...")

    response_text = call_yandex_gpt(system_prompt, user_prompt, temperature=0.5)

    if not response_text:
        return "Извините, у меня возникла небольшая техническая проблема. Давайте продолжим. Расскажите о вашем последнем проекте."

    return response_text.strip()


def analyze_interview_transcript(
        transcript: str,
        vacancy_details: dict,
        screening_report: dict
) -> dict | None:
    system_prompt = (
        "Ты — ведущий HR-эксперт с 15-летним опытом в IT-рекрутинге. "
        "Твоя задача — провести глубокий и объективный анализ записи собеседования. "
        "Проанализируй диалог между AI-аватаром и кандидатом. Оцени ответы кандидата по ключевым компетенциям, "
        "приводя в качестве доказательств его цитаты. "
        "Сформируй итоговый балл, краткое саммари, сильные и слабые стороны и дай четкую рекомендацию. "
        "Твой ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON-объекта. "
        "Не используй разметку Markdown, вводные фразы или любые символы до или после JSON-объекта."
    )

    user_prompt = f"""
    Проанализируй транскрипцию интервью и верни JSON по следующей структуре:
    {{
      "overall_score": <number, итоговый балл от 0 до 100>,
      "summary": "<string, общее впечатление о кандидате в 3-4 предложениях>",
      "competency_analysis": [
        {{
          "criterion": "<название критерия из вакансии>",
          "score": <number, оценка по этому критерию от 0 до 10>,
          "assessment": "<string, детальное обоснование оценки с примерами и цитатами из диалога>"
        }}
      ],
      "strengths": ["<список из 2-3 ключевых сильных сторон кандидата>"],
      "weaknesses": ["<список из 2-3 зон для роста или выявленных пробелов>"],
      "recommendation": "<'Рекомендуем к следующему этапу' | 'Отказ' | 'Требуется дополнительная проверка'>"
    }}

    КОНТЕКСТ ДЛЯ АНАЛИЗА:

    1. Требования вакансии:
    ---
    {json.dumps(vacancy_details, ensure_ascii=False, indent=2)}
    ---

    2. Первичный анализ резюме (для справки):
    ---
    {json.dumps(screening_report, ensure_ascii=False, indent=2)}
    ---

    3. Полная транскрипция собеседования:
    ---
    {transcript}
    ---
    """

    print("Отправка запроса на финальный анализ интервью в YandexGPT...")
    response_text = call_yandex_gpt(system_prompt, user_prompt, temperature=0.2)

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
        print(f"Ошибка парсинга JSON из ответа LLM при анализе интервью: {e}")
        print(f"Полученный ответ (до очистки): {response_text}")
        return None


def analyze_interrupted_transcript(transcript: str) -> dict | None:
    """
    Проводит "дешевый" анализ прерванной транскрипции интервью.

    Задача этой функции — не оценивать кандидата, а предоставить HR
    краткую выжимку того, что успели обсудить до прерывания сессии.

    Args:
        transcript: Полный текст транскрипции диалога.

    Returns:
        Словарь с саммари и заметками о прерывании, либо None в случае ошибки.
    """
    system_prompt = (
        "Ты — AI-ассистент, специализирующийся на анализе текста. "
        "Твоя задача — быстро и кратко суммировать содержание диалога. "
        "Твой ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON-объекта. "
        "Не используй разметку Markdown, вводные фразы или любые символы до или после JSON-объекта."
    )

    user_prompt = f"""
    Проанализируй текст **прерванного** интервью между AI-аватаром и кандидатом.
    Не нужно ставить оценки, анализировать компетенции или давать рекомендации.

    Твоя задача — выполнить три действия:
    1. В поле `summary` напиши очень краткую выжимку (2-3 предложения) того, какие темы были затронуты и что кандидат успел о себе рассказать.
    2. В поле `status_note` вставь точную фразу: "Интервью было прервано. Данный отчет является предварительным и не содержит оценок."
    3. В поле `recommendation` вставь точную фразу: "Требуется ручная проверка HR-специалистом."

    Верни результат в формате JSON со следующей структурой:
    {{
      "summary": "<краткая выжимка диалога>",
      "status_note": "Интервью было прервано. Данный отчет является предварительным и не содержит оценок.",
      "recommendation": "Требуется ручная проверка HR-специалистом."
    }}

    Вот транскрипция для анализа:
    ---
    {transcript}
    ---
    """

    print("Отправка запроса на предварительный анализ прерванного интервью в YandexGPT...")
    response_text = call_yandex_gpt(system_prompt, user_prompt, temperature=0.3)

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
        print(f"Ошибка парсинга JSON из ответа LLM при анализе прерванного интервью: {e}")
        print(f"Полученный ответ (до очистки): {response_text}")
        return None