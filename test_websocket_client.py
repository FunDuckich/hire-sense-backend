import asyncio
import websockets
import json
import requests
from urllib.parse import quote

# --- НАСТРОЙКИ (убедись, что они верны) ---
BASE_URL = "http://localhost:8000"
CANDIDATE_EMAIL = "candidate@mail.com"
CANDIDATE_PASSWORD = "securepassword456"
APPLICATION_ID = 4
AUDIO_FILE_PATH = "test_audio.ogg"
CHUNK_SIZE = 4096


def get_access_token(email, password):
    print("--- Шаг 1: Получение токена доступа ---")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": email, "password": password})
        response.raise_for_status()
        token = response.json()["access_token"]
        print("Токен успешно получен.")
        return token
    except requests.exceptions.RequestException as e:
        print(f"!!! ОШИБКА при логине: {e.response.text if e.response else e}")
        return None


def start_interview_session(application_id, token):
    print(f"\n--- Шаг 2: Запуск сессии интервью для отклика #{application_id} ---")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(f"{BASE_URL}/api/v1/applications/{application_id}/start-interview", headers=headers)
        response.raise_for_status()
        session_id = response.json()["interview_session_id"]
        print(f"Сессия интервью #{session_id} успешно создана.")
        return session_id
    except requests.exceptions.RequestException as e:
        print(f"!!! ОШИБКА при старте интервью: {e.response.text if e.response else e}")
        return None


async def run_interview_ws(session_id, token):
    safe_token = quote(token)
    uri = f"ws://localhost:8000/api/v1/ws/{session_id}?token={safe_token}"
    print(f"\n--- Шаг 3: Подключение к WebSocket ---")

    try:
        async with websockets.connect(uri) as websocket:
            print("Успешно подключено!")

            # --- НОВЫЙ, ПРОСТОЙ ЦИКЛ ---
            while True:
                # 1. Ждем сообщение от сервера. Любое.
                message_raw = await websocket.recv()
                message_data = json.loads(message_raw)
                print(f"<-- От сервера: Тип: {message_data.get('type')}, Текст: '{message_data.get('text', '')}'")

                # 2. ЕСЛИ это вопрос от аватара, ТОГДА отвечаем.
                if message_data.get('type') == 'avatar_speech':
                    print(f"--> Отвечаем на вопрос, отправляем аудио: {AUDIO_FILE_PATH}")
                    with open(AUDIO_FILE_PATH, "rb") as f:
                        while chunk := f.read(CHUNK_SIZE):
                            await websocket.send(chunk)

                    # 3. После аудио ОБЯЗАТЕЛЬНО отправляем сигнал конца.
                    await websocket.send(json.dumps({"type": "stream_end"}))
                    print("--> Отправлен сигнал stream_end.")

    except websockets.ConnectionClosed as e:
        print(f"\n--- Соединение штатно закрыто сервером (интервью окончено): Код {e.code} - {e.reason} ---")
    except Exception as e:
        print(f"!!! ОШИБКА WebSocket: {e}")


async def main():
    token = get_access_token(CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
    if not token: return

    session_id = start_interview_session(APPLICATION_ID, token)
    if not session_id: return

    await run_interview_ws(session_id, token)


if __name__ == "__main__":
    asyncio.run(main())
