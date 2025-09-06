import json
import time
from datetime import datetime
import jwt
import requests
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


def _call_yandex_gpt(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str | None:
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
        return response.json()['result']['alternatives'][0]['message']['text']
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP ошибка при вызове YandexGPT: {http_err}")
        print(f"Тело ответа: {http_err.response.text}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при вызове YandexGPT: {e}")
        return None


def _call_yandex_gpt_and_parse_json(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict | None:
    response_text = _call_yandex_gpt(system_prompt, user_prompt, temperature)
    if not response_text:
        return None

    try:
        clean_response = response_text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_response)
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON из ответа LLM: {e}")
        print(f"Полученный ответ: {response_text}")
        return None


def analyze_resume(vacancy_details: dict, resume_md: str) -> dict | None:
    system_prompt = (
        "Ты — HR-аналитик. Проведи скрининг резюме. "
        "Ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON. Без Markdown и лишних слов."
    )
    user_prompt = f"""
    Проанализируй резюме на соответствие вакансии.
    В `overall_match_score` поставь число от 0 до 100.
    В `summary` напиши краткий вывод.
    В `questions_to_ask` сформулируй 3-4 ключевых вопроса для интервью.
    Структура JSON:
    {{
      "overall_match_score": <number>,
      "summary": "<string>",
      "competency_check": [
        {{ "criterion": "<название критерия>", "confirmed": <boolean>, "evidence": "<обоснование>" }}
      ],
      "questions_to_ask": ["<вопрос 1>", "<вопрос 2>"],
      "red_flags": ["<список проблем, если есть>"]
    }}

    Требования вакансии:
    ---
    {json.dumps(vacancy_details, ensure_ascii=False, indent=2)}
    ---
    Резюме кандидата:
    ---
    {resume_md}
    ---
    """
    return _call_yandex_gpt_and_parse_json(system_prompt, user_prompt, temperature=0.4)


def get_interview_response(history: list[dict], vacancy_details: dict, resume_summary: dict) -> str:
    system_prompt = (
        "Ты — HR-аватар Алекс. Веди первичное собеседование. Будь профессионален, вежлив, дружелюбен. "
        "Задавай по ОДНОМУ открытому вопросу за раз. Твоя цель — раскрыть опыт кандидата. "
        "Если ответ короткий, задай уточняющий вопрос по той же теме. Не повторяйся."
    )
    vacancy_context = json.dumps(vacancy_details, ensure_ascii=False, indent=2)
    resume_context = json.dumps(resume_summary, ensure_ascii=False, indent=2)
    user_prompt = f"""
    Информация о вакансии:
    ---
    {vacancy_context}
    ---
    Выжимка из резюме и вопросы для уточнения:
    ---
    {resume_context}
    ---
    История диалога:
    ---
    {json.dumps(history, ensure_ascii=False, indent=2)}
    ---
    ЗАДАЧА: Сгенерируй СЛЕДУЮЩИЙ ОДИН вопрос или реплику для кандидата.
    Твой ответ должен быть только текстом вопроса. Без лишних слов, вроде "Хорошо, следующий вопрос:".
    """

    response_text = _call_yandex_gpt(system_prompt, user_prompt, temperature=0.5)

    if not response_text:
        return "Понятно, спасибо. Расскажите, пожалуйста, о проекте, которым вы больше всего гордитесь."

    return response_text


def analyze_interview_transcript(transcript: str, vacancy_details: dict, screening_report: dict) -> dict | None:
    system_prompt = (
        "Ты — ведущий HR-эксперт в IT-рекрутинге. Проведи глубокий, объективный анализ транскрипции интервью. "
        "Твоя задача — оценить hard skills и soft skills кандидата исключительно на основе текста его ответов. "
        "Ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON. Без Markdown и лишних слов."
    )
    user_prompt = f"""
    Проанализируй транскрипцию интервью. Верни JSON по следующей структуре:
    {{
      "overall_score": <number, 0-100, общая оценка кандидата>,
      "summary": "<string, общее впечатление о кандидате в 3-4 предложениях>",
      "hard_skills_analysis": {{ 
          "score": <number, 0-10>, 
          "assessment": "<string, детальное обоснование оценки, ОБЯЗАТЕЛЬНО включая 1-2 прямые цитаты из ответов кандидата, подтверждающие твой вывод>" 
      }},
      "soft_skills_analysis": {{
          "confidence_score": <number, 0-10, оценка уверенности по тексту>,
          "proactivity_score": <number, 0-10, оценка проактивности и ориентации на результат>,
          "attitude_score": <number, 0-10, оценка отношения к прошлому опыту и команде>,
          "assessment": "<string, общий вывод по soft skills, ОБЯЗАТЕЛЬНО приводя примеры фраз-маркеров, найденных в тексте>"
      }},
      "strengths": ["<список из 2-3 ключевых сильных сторон>"],
      "weaknesses": ["<список из 2-3 зон для роста>"],
      "recommendation": "<'Рекомендуем к следующему этапу' | 'Отказ' | 'Требуется дополнительная проверка'>"
    }}

    ИНСТРУКЦИИ ПО АНАЛИЗУ SOFT SKILLS:
    - Уверенность: Ищи маркеры неуверенности ("наверное", "вроде бы", "возможно"). Чем их меньше, тем выше балл.
    - Проактивность: Ищи активные глаголы и маркеры достижений ("реализовал", "внедрил", "оптимизировал", "увеличил результат на X%"). Оцени, говорит ли кандидат о процессе или о результате.
    - Отношение: Анализируй, как кандидат говорит о прошлых местах работы. Ищи маркеры негатива ("плохой менеджмент") или конструктивные выводы.

    КОНТЕКСТ:
    1. Требования вакансии: {json.dumps(vacancy_details, ensure_ascii=False)}
    2. Первичный анализ резюме: {json.dumps(screening_report, ensure_ascii=False)}
    3. Полная транскрипция собеседования:
    ---
    {transcript}
    ---
    """
    return _call_yandex_gpt_and_parse_json(system_prompt, user_prompt, temperature=0.2)


def analyze_interrupted_transcript(transcript: str) -> dict | None:
    system_prompt = (
        "Ты — AI-ассистент. Твоя задача — быстро суммировать содержание диалога. "
        "Ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON. Без Markdown и лишних слов."
    )
    user_prompt = f"""
    Проанализируй текст ПРЕРВАННОГО интервью. Не ставь оценок и не давай рекомендаций.
    Просто сделай краткую выжимку того, что успели обсудить.
    Верни JSON по следующей структуре:
    {{
      "status_note": "Интервью было прервано кандидатом. Данный отчет является предварительным и не содержит оценок.",
      "summary": "<краткая выжимка диалога в 2-3 предложениях>"
    }}

    Транскрипция для анализа:
    ---
    {transcript}
    ---
    """
    return _call_yandex_gpt_and_parse_json(system_prompt, user_prompt, temperature=0.3)


def check_interview_completion(dialogue_history: list[dict], vacancy_details: dict) -> str:
    system_prompt = (
        "Ты — HR-супервайзер, наблюдающий за ходом интервью. Твоя задача — решить, нужно ли продолжать диалог. "
        "Проанализируй диалог и ключевые требования вакансии. "
        "Ответь ТОЛЬКО ОДНИМ СЛОВОМ: CONTINUE или FINISH."
    )

    criteria = [crit.get("criterion") for crit in vacancy_details.get("evaluation_criteria", [])]

    user_prompt = f"""
    КЛЮЧЕВЫЕ ТРЕБОВАНИЯ ВАКАНСИИ, которые нужно проверить:
    - {", ".join(criteria) if criteria else "Общие компетенции"}

    ИСТОРИЯ ДИАЛОГА:
    ---
    {json.dumps(dialogue_history, ensure_ascii=False, indent=2)}
    ---

    ЗАДАЧА: Покрыты ли в диалоге все ключевые требования?
    - Если нужно задать еще вопросы, чтобы раскрыть темы глубже или покрыть все требования, ответь: CONTINUE.
    - Если кандидат уже предоставил достаточно информации по всем ключевым требованиям, ответь: FINISH.
    """

    decision = _call_yandex_gpt(system_prompt, user_prompt, temperature=0.1)

    if decision and "FINISH" in decision.upper():
        return "FINISH"

    return "CONTINUE"


def is_answer_relevant(last_question: str, last_answer: str) -> bool:
    system_prompt = (
        "Ты — AI-аналитик. Твоя задача — оценить релевантность ответа на вопрос. "
        "Ответь ТОЛЬКО ОДНИМ СЛОВОМ: YES или NO."
    )
    user_prompt = f"""
    ВОПРОС: "{last_question}"
    ОТВЕТ: "{last_answer}"

    ЗАДАЧА: Является ли ОТВЕТ релевантным ответом на ВОПРОС?
    - Если да, или если это общая фраза, но по теме, ответь: YES.
    - Если ответ совершенно не по теме или является явным уклонением, ответь: NO.
    """
    response = _call_yandex_gpt(system_prompt, user_prompt, temperature=0.0)
    return response and "YES" in response.upper()


def analyze_candidate_behavior(dialogue_history: list[dict]) -> dict | None:
    system_prompt = (
        "Ты — AI-супервайзер, анализирующий диалог интервью в реальном времени. "
        "Твоя задача — оценить поведение кандидата в его ПОСЛЕДНЕЙ реплике. "
        "Ответ ДОЛЖЕН БЫТЬ ТОЛЬКО в формате валидного JSON."
    )

    last_exchange = dialogue_history[-2:] if len(dialogue_history) >= 2 else dialogue_history

    user_prompt = f"""
    Проанализируй ПОСЛЕДНЮЮ реплику кандидата в этом диалоге:
    ---
    {json.dumps(last_exchange, ensure_ascii=False, indent=2)}
    ---

    Верни JSON-объект со следующими boolean-флагами:
    - "is_toxic": true, если кандидат использует ненормативную лексику, оскорбления или проявляет агрессию.
    - "is_off_topic": true, если кандидат явно уклоняется от ответа на заданный аватаром вопрос или говорит на совершенно постороннюю тему.
    - "wants_to_finish": true, если кандидат прямо просит или намекает на желание завершить интервью (например, "у меня больше нет времени", "давайте закончим").

    Пример ответа: {{"is_toxic": false, "is_off_topic": true, "wants_to_finish": false}}
    """

    behavior_flags = _call_yandex_gpt_and_parse_json(system_prompt, user_prompt, temperature=0.1)

    return behavior_flags or {"is_toxic": False, "is_off_topic": False, "wants_to_finish": False}
