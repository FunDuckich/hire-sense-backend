import time
import json
import requests
import jwt

from app.core.config import settings

_iam_token_cache = {
    "token": None,
    "expires_at": 0
}


def get_iam_token() -> str:
    now = int(time.time())
    if _iam_token_cache["token"] is None or _iam_token_cache["expires_at"] <= now + 60:
        print("Обновление IAM-токена...")
        try:
            with open("authorized_key.json", 'r') as key_file:
                private_key_data = json.load(key_file)
                private_key = private_key_data["private_key"]

            payload = {
                'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                'iss': settings.YC_SERVICE_ACCOUNT_ID,
                'iat': now,
                'exp': now + 3600
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

            _iam_token_cache["token"] = result["iamToken"]

            token_payload = jwt.decode(result["iamToken"], options={"verify_signature": False})
            _iam_token_cache["expires_at"] = token_payload.get("exp", 0)
            print("IAM-токен успешно обновлен.")

        except Exception as e:
            print(f"Ошибка получения IAM-токена: {e}")
            if _iam_token_cache["token"]:
                return _iam_token_cache["token"]
            raise

    return _iam_token_cache["token"]

class MockLLMService:
    def __init__(self):
        self.responses = [
            "Понятно, спасибо. А расскажите подробнее о вашем опыте с Python.",
            "Очень интересно. Можете привести конкретный пример из проекта?",
            "Хорошо. А как вы решали конфликты в команде?",
            "Принято. Какие ваши ожидания по заработной плате?",
            "Спасибо за ваши ответы. На этом у меня все. Мы с вами свяжемся."
        ]
        self.current_index = 0

    async def get_next_response(self, history: list[dict]) -> str:
        """
        Возвращает следующий ответ из списка.
        `history` пока не используется, но понадобится для реального LLM.
        """
        if self.current_index < len(self.responses):
            response = self.responses[self.current_index]
            self.current_index += 1
            return response
        else:
            return "К сожалению, мои вопросы закончились. Спасибо за интервью!"