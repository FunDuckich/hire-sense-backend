import asyncio
import websockets
import json
import requests
import time
import sys
from urllib.parse import quote

# --- НАСТРОЙКИ ---
BASE_URL = "http://localhost:8000"
SHOULD_SETUP_ENTITIES = True
EXISTING_APPLICATION_ID = 1  # Используется, если SHOULD_SETUP_ENTITIES = False

HR_EMAIL = "hr@hire-sense.com"
HR_PASSWORD = "password123"
CANDIDATE_EMAIL = "dev@python.com"
CANDIDATE_PASSWORD = "password456"

RESUME_PATH = "resume.pdf"
SCENARIOS = {
    "happy_path": [{"file": "answer_good.ogg", "description": "Релевантный ответ"}],
    "deep": [
        {"file": "answer_good.ogg", "description": "Релевантный ответ 1 (проверка asyncio)"},
        {"file": "answer_good.ogg", "description": "Релевантный ответ 2 (проверка Docker)"}
    ],
    "off_topic": [
        {"file": "answer_off_topic.ogg", "description": "Нерелевантный ответ 1 (ожидаем предупреждение)"},
        {"file": "answer_off_topic.ogg", "description": "Нерелевантный ответ 2 (ожидаем завершение)"}
    ],
    "toxic": [{"file": "answer_toxic.ogg", "description": "Токсичный ответ (ожидаем немедленное завершение)"}]
}
CHUNK_SIZE = 4096


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_access_token(email, password, user_type="User"):
    print(f"--- Шаг: Получение токена для '{user_type}' ---")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": email, "password": password})
        response.raise_for_status()
        print("Токен успешно получен.")
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        print(f"!!! ОШИБКА LOGIN: {e.response.text if e.response else e}");
        raise


def setup_environment():
    print("--- НАЧАЛО ПОДГОТОВКИ ОКРУЖЕНИЯ ---")
    requests.post(f"{BASE_URL}/api/v1/auth/hr/register",
                  json={"email": HR_EMAIL, "name": "Тестовый HR", "password": HR_PASSWORD, "company_name": "Тест Inc.",
                        "role": "HR"})
    requests.post(f"{BASE_URL}/api/v1/auth/candidate/register",
                  json={"email": CANDIDATE_EMAIL, "name": "Тестовый Кандидат", "password": CANDIDATE_PASSWORD,
                        "role": "CANDIDATE"})

    hr_token = get_access_token(HR_EMAIL, HR_PASSWORD, "HR")

    print("\n--- Шаг: Создание вакансии ---")
    vacancy_payload = {
        "job_title": "Senior Python Developer", "complexity": "Senior",
        "tech_stack": "FastAPI, asyncio, pytest, Docker",
        "evaluation_criteria": [
            {"criterion": "Глубокое знание asyncio", "weight": 60},
            {"criterion": "Опыт контейнеризации с Docker", "weight": 40}
        ]
    }
    response = requests.post(f"{BASE_URL}/api/v1/vacancies/", headers={"Authorization": f"Bearer {hr_token}"},
                             json=vacancy_payload)
    response.raise_for_status();
    vacancy_id = response.json()["id"];
    print(f"Вакансия #{vacancy_id} создана.")

    candidate_token = get_access_token(CANDIDATE_EMAIL, CANDIDATE_PASSWORD, "Кандидат")

    print(f"\n--- Шаг: Отклик на вакансию #{vacancy_id} ---")
    with open(RESUME_PATH, 'rb') as f:
        files = {'resume_file': ('resume.pdf', f, 'application/pdf')}
        response = requests.post(f"{BASE_URL}/api/v1/vacancies/{vacancy_id}/apply",
                                 headers={"Authorization": f"Bearer {candidate_token}"}, files=files)
        response.raise_for_status();
        application_id = response.json()["application_id"]

    print(f"Отклик #{application_id} создан. Ожидание 30 сек для скрининга...")
    time.sleep(30)
    print("--- ПОДГОТОВКА ЗАВЕРШЕНА ---")
    return candidate_token, application_id


def start_interview_session(token, application_id):
    print(f"\n--- Шаг: Запуск сессии для отклика #{application_id} ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/v1/applications/{application_id}/start-interview", headers=headers)
    response.raise_for_status()
    session_id = response.json()["interview_session_id"]
    print(f"Сессия интервью #{session_id} создана.")
    return session_id


async def run_interview_ws(session_id, token, answers_sequence):
    safe_token = quote(token)
    uri = f"ws://localhost:8000/api/v1/ws/{session_id}?token={safe_token}"
    print(f"\n--- Шаг: Подключение к WebSocket ---")

    try:
        async with websockets.connect(uri) as websocket:
            print("Успешно подключено!")

            for answer_info in answers_sequence:
                # 1. Ждем вопрос/реплику аватара
                while True:
                    message_raw = await websocket.recv()
                    message_data = json.loads(message_raw)
                    print(f"<-- От сервера: {message_data.get('type')}: '{message_data.get('text', '')}'")
                    if message_data.get('type') == 'avatar_speech':
                        text = message_data.get('text', '')
                        if "На этом у меня все вопросы" in text or "вынужден прервать" in text or "не можем продолжить" in text:
                            print("--- Получена финальная фраза от аватара. Завершение теста. ---")
                            return  # <-- ВЫХОДИМ ИЗ ВСЕЙ ФУНКЦИИ
                        break

                print(f"\n--- Итерация: {answer_info['description']} ---")

                # 2. Отвечаем аудио
                audio_file = answer_info["file"]
                print(f"--> Отправка аудио: {audio_file}")
                with open(audio_file, "rb") as f:
                    while chunk := f.read(CHUNK_SIZE):
                        await websocket.send(chunk)

                # 3. Отправляем сигнал конца
                await websocket.send(json.dumps({"type": "stream_end"}))
                print("--> Отправлен сигнал stream_end.")

            print("\n--- Все ответы по сценарию отправлены. Ждем финальной фразы от сервера... ---")
            while True:
                message_raw = await websocket.recv()
                message_data = json.loads(message_raw)
                print(f"<-- От сервера: {message_data.get('type')}: '{message_data.get('text', '')}'")
                if message_data.get('type') == 'avatar_speech':
                    text = message_data.get('text', '')
                    if "всего доброго" in text.lower() or "хорошего дня" in text.lower() or "на этом у меня все" in text.lower() or "вынужден прервать" in text.lower():
                        print("--- Получена финальная фраза от аватара. Завершение теста. ---")
                        return

    except websockets.ConnectionClosed as e:
        print(f"\n--- Соединение штатно закрыто сервером: Код {e.code} - {e.reason} ---")
    except Exception as e:
        print(f"!!! ОШИБКА WebSocket: {e}");
        raise
    finally:
        print("--- ТЕСТ ЗАВЕРШЕН! ---")


async def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SCENARIOS:
        print(f"Ошибка: Укажите сценарий: {', '.join(SCENARIOS.keys())}");
        return

    scenario_key = sys.argv[1]
    answers_to_send = SCENARIOS[scenario_key]
    print(f"--- ЗАПУСК СЦЕНАРИЯ: '{scenario_key.upper()}' ---")

    token, app_id = (None, None)
    if SHOULD_SETUP_ENTITIES:
        try:
            token, app_id = setup_environment()
        except Exception as e:
            print(f"!!! КРИТИЧЕСКАЯ ОШИБКА подготовки: {e}");
            return
    else:
        app_id = EXISTING_APPLICATION_ID
        token = get_access_token(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)

    if not (token and app_id): print("Тест прерван."); return

    session_id = start_interview_session(token, app_id)
    if not session_id: return

    await run_interview_ws(session_id, token, answers_to_send)


if __name__ == "__main__":
    asyncio.run(main())
