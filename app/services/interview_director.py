from sqlalchemy.orm import Session
from app.models.interview import TranscriptRole
from app.repositories.interview_repository import InterviewRepository
from app.services import tts_service, llm_service


class MockLLMService:
    async def get_next_response(self, history: list) -> str:
        last_message = history[-1].get("content", "").lower() if history else ""
        if "о себе" in last_message or not history:
            return "Спасибо. Расскажите о вашем самом успешном проекте."
        elif "проект" in last_message:
            return "Звучит интересно. А какие технологии вы использовали?"
        else:
            return "Понятно. А что вы можете рассказать о вашем опыте с SQL?"


class InterviewDirector:
    def __init__(self, session_id: int, db: Session):
        if not session_id:
            raise ValueError("session_id must be provided")

        self.session_id = session_id
        self.db = db
        self.interview_repo = InterviewRepository(db)
        self.llm_service = MockLLMService()  # Используем нашу заглушку
        self.dialogue_history = []
        self._initialize_history()

    def _initialize_history(self):
        system_prompt = {"role": "system", "content": "Ты - HR-аватар. Веди диалог с кандидатом."}
        self.dialogue_history.append(system_prompt)

    async def start(self) -> tuple[bytes | None, str]:
        greeting_text = "Здравствуйте! Меня зовут Алекс, я ваш AI-интервьюер. Давайте начнем. Расскажите немного о себе."

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=greeting_text
        )
        self.dialogue_history.append({"role": "assistant", "content": greeting_text})

        # --- ИСПРАВЛЕННЫЙ ВЫЗОВ TTS ---
        # Теперь это не асинхронный вызов, а синхронный, как и был в коде BE2
        audio_data = tts_service.synthesize_speech_rest_v3(greeting_text)

        return audio_data, greeting_text

    async def handle_candidate_response(self, text: str) -> tuple[bytes | None, str]:
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.CANDIDATE, message=text
        )
        self.dialogue_history.append({"role": "user", "content": text})

        next_question = await self.llm_service.get_next_response(self.dialogue_history)

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=next_question
        )
        self.dialogue_history.append({"role": "assistant", "content": next_question})

        audio_data = tts_service.synthesize_speech_rest_v3(next_question)

        return audio_data, next_question
