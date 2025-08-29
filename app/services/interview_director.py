from sqlalchemy.orm import Session
from app.models.interview import TranscriptRole
from app.repositories.interview_repository import InterviewRepository
from app.services.llm_service import MockLLMService
# Предполагается, что твои сервисы STT/TTS можно импортировать так.
# Если у тебя там функции, а не классы, адаптируем.
from app.services.tts_service import TTSService
from app.services.stt_service import STTService

# TODO Важное примечание: я предположил, что твои TTSService и STTService — это классы,
#  которые можно инстанцировать. Если это просто функции, код нужно будет немного адаптировать
#  (например, просто вызывать await tts_service.synthesize(...)). Также я предположил,
#  что метод синтеза речи называется synthesize и он асинхронный.
#  Адаптируй названия методов под свой реальный код.


class InterviewDirector:
    def __init__(self, session_id: int, db: Session):
        if not session_id:
            raise ValueError("session_id must be provided")

        self.session_id = session_id
        self.db = db

        # Инициализируем все необходимые компоненты
        self.interview_repo = InterviewRepository(db)
        self.llm_service = MockLLMService()
        self.tts_service = TTSService()
        # STTService нам здесь не нужен, так как распознанный текст приходит извне

        # История диалога для передачи в LLM
        self.dialogue_history = []
        # Можно добавить системный промпт, даже для заглушки
        self._initialize_history()

    def _initialize_history(self):
        """Задает начальный системный промпт."""
        system_prompt = {
            "role": "system",
            "content": "Ты - HR-аватар. Веди диалог с кандидатом."
        }
        self.dialogue_history.append(system_prompt)

    async def start(self) -> tuple[bytes, str]:
        """
        Начинает интервью: генерирует приветствие, синтезирует речь.
        Возвращает кортеж (аудио_данные, текст_сообщения).
        """
        print(f"[Director] Starting interview for session {self.session_id}")

        # 1. Формируем приветственное сообщение
        greeting_text = "Здравствуйте! Меня зовут Алекс, я ваш AI-интервьюер. Давайте начнем. Расскажите немного о себе."

        # 2. Сохраняем реплику аватара в транскрипцию
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id,
            role=TranscriptRole.AVATAR,
            message=greeting_text
        )
        self.dialogue_history.append({"role": "assistant", "content": greeting_text})

        # 3. Синтезируем речь
        audio_data = await self.tts_service.synthesize(greeting_text)

        print(f"[Director] Greeting synthesized, sending to client.")
        return audio_data, greeting_text

    async def handle_candidate_response(self, text: str) -> tuple[bytes, str]:
        """
        Обрабатывает распознанный текст ответа кандидата.
        Возвращает кортеж (аудио_данные_ответа_аватара, текст_ответа_аватара).
        """
        print(f"[Director] Handling candidate response: '{text}'")

        # 1. Сохраняем реплику кандидата
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id,
            role=TranscriptRole.CANDIDATE,
            message=text
        )
        self.dialogue_history.append({"role": "user", "content": text})

        # 2. Получаем следующий вопрос от LLM (пока что от заглушки)
        next_question = await self.llm_service.get_next_response(self.dialogue_history)
        print(f"[Director] LLM response: '{next_question}'")

        # 3. Сохраняем реплику аватара
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id,
            role=TranscriptRole.AVATAR,
            message=next_question
        )
        self.dialogue_history.append({"role": "assistant", "content": next_question})

        # 4. Синтезируем речь для следующего вопроса
        audio_data = await self.tts_service.synthesize(next_question)

        print(f"[Director] Next question synthesized, sending to client.")
        return audio_data, next_question