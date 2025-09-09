from typing import Optional, Any
from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    MAX_INTERVIEW_DURATION_SECONDS: int = 1200
    SCREENING_THRESHOLD_SCORE: int = 50
    MAX_IRRELEVANT_ANSWERS: int = 2
    CANDIDATE_SILENCE_TIMEOUT_SECONDS: float = 15.0
    MAX_SILENCE_PROMPTS: int = 3
    YANDEX_STT_EOU_PAUSE_MS: int = 2500
    WEBSOCKET_RECEIVE_TIMEOUT_SECONDS: float = 1.5
    MAX_SILENCE_ITERATIONS_BEFORE_BREAK: int = 3

    YC_FOLDER_ID: str

    @computed_field
    @property
    def YC_MODEL_URI(self) -> str:
        return f"gpt://{self.YC_FOLDER_ID}/yandexgpt/latest"

    @computed_field
    @property
    def YC_MODEL_URI_LITE(self) -> str:
        return f"gpt://{self.YC_FOLDER_ID}/yandexgpt-lite/latest"

    YC_SERVICE_ACCOUNT_ID: str
    YC_KEY_ID: str
    YC_SA_KEY_FILE_PATH: str = "authorized_key.json"

    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_SENDER: Optional[str] = None

    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v == "":
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
    )


settings = Settings()