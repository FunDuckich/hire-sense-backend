from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    MAX_INTERVIEW_DURATION_SECONDS: int = 1200

    YC_SERVICE_ACCOUNT_ID: str
    YC_KEY_ID: str
    YC_FOLDER_ID: str
    YC_SA_KEY_FILE_PATH: str = "authorized_key.json"

    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_SENDER: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

print(f"SECRET_KEY: {settings.SECRET_KEY}, ALGORITHM: {settings.ALGORITHM}")
