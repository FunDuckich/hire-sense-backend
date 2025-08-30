import asyncio
import json

from sqlalchemy.orm import Session, joinedload
from app.models.interview import TranscriptRole
from app.repositories.interview_repository import InterviewRepository
from app.services import tts_service, llm_service


class InterviewDirector:
    def __init__(self, session_id: int, db: Session):
        if not session_id:
            raise ValueError("session_id must be provided")

        self.session_id = session_id
        self.db = db
        self.interview_repo = InterviewRepository(db)

        # --- НОВАЯ ЛОГИКА ЗАГРУЗКИ КОНТЕКСТА ---
        self.vacancy_details = {}
        self.resume_summary = {}
        self._load_context()  # Вызываем новый метод для загрузки

        self.dialogue_history = []
        self._initialize_history()

    def _load_context(self):
        print(f"[Director] Загрузка контекста для сессии {self.session_id}...")

        session = self.interview_repo.get_session_with_details(self.session_id)

        if not session:
            raise ValueError(f"InterviewSession с ID {self.session_id} не найдена.")

        application = session.application
        if not application:
            raise ValueError("С сессией не связана заявка (application).")

        vacancy = application.vacancy
        if vacancy:
            self.vacancy_details = {
                "job_title": vacancy.job_title,
                "required_experience": vacancy.required_experience,
                "hard_skills": vacancy.hard_skills,
                "evaluation_criteria": [{"criterion": c.criterion} for c in vacancy.evaluation_criteria]
            }

        screening_result = application.screening_result
        if screening_result and screening_result.result_json:
            result_data = screening_result.result_json
            if isinstance(result_data, str):
                try:
                    result_data = json.loads(result_data)
                except json.JSONDecodeError:
                    result_data = {}

            self.resume_summary = {
                "summary": result_data.get("summary", ""),
                "questions_to_ask": result_data.get("questions_to_ask", [])
            }
        print("[Director] Контекст успешно загружен.")

    async def start(self) -> tuple[bytes | None, str]:
        print(f"[Director] Начинаем интервью для сессии {self.session_id}")
        initial_questions = self.resume_summary.get("questions_to_ask", [])
        if initial_questions:
            first_question = initial_questions[0]
            greeting_text = f"Здравствуйте! Меня зовут Алекс, я ваш AI-интервьюер. Давайте начнем. {first_question}"
        else:
            greeting_text = "Здравствуйте! Меня зовут Алекс, я ваш AI-интервьюер. Давайте начнем. Расскажите немного о себе."

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=greeting_text
        )
        self.dialogue_history.append({"role": "assistant", "content": greeting_text})

        import asyncio
        loop = asyncio.get_running_loop()
        audio_data = await loop.run_in_executor(None, tts_service.synthesize_speech, greeting_text)

        return audio_data, greeting_text

    async def handle_candidate_response(self, text: str) -> tuple[bytes | None, str]:
        print(f"[Director] Обработка ответа кандидата: '{text}'")

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.CANDIDATE, message=text
        )
        self.dialogue_history.append({"role": "user", "content": text})

        import asyncio
        loop = asyncio.get_running_loop()
        next_question = await loop.run_in_executor(
            None,
            llm_service.get_interview_response,
            self.dialogue_history,
            self.vacancy_details,
            self.resume_summary
        )

        if not next_question:
            next_question = "Понятно, спасибо. Давайте перейдем к следующему вопросу."

        print(f"[Director] Ответ LLM: '{next_question}'")

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=next_question
        )
        self.dialogue_history.append({"role": "assistant", "content": next_question})

        audio_data = await loop.run_in_executor(None, tts_service.synthesize_speech, next_question)

        return audio_data, next_question
