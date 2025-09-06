from jose import jwt, JWTError
from app.core.config import settings

TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjYW5kaWRhdGVAbWFpbC5jb20iLCJleHAiOjE3NTcxMDE3NTN9.Utv2xg1mQE02V9-wP5cBgKrwXALXd8co-Q8drfZiTEA"

print(f"--- Проверка токена ---")
print(f"Используемый SECRET_KEY: '...{settings.SECRET_KEY[-5:]}'")
print(f"Используемый ALGORITHM: {settings.ALGORITHM}")

try:
    payload = jwt.decode(
        TEST_TOKEN,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM]
    )
    print("\n[ SUCCESS ] Токен успешно декодирован!")
    print("Содержимое (payload):", payload)

except JWTError as e:
    print(f"\n[ FAILED ] Ошибка декодирования токена: {e}")
