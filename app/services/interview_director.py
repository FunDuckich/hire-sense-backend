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

        self.vacancy_details = {}
        self.resume_summary = {}
        self._load_context()

        # --- НОВЫЙ БЛОК: Загрузка контекста при инициализации ---
        self.context = self._load_context()
        if not self.context:
            raise ValueError(f"Could not load context for session_id {self.session_id}")
        # --------------------------------------------------------

        self.dialogue_history = []
        self._initialize_history()

    def _load_context(self) -> dict:
        """
        Загружает весь необходимый контекст для интервью из БД.
        """
        print(f"[Director] Loading context for session {self.session_id}")
        session_details = self.interview_repo.get_session_with_details(self.session_id)

        if not session_details:
            return {}

        application = session_details.application
        vacancy = application.vacancy
        candidate = application.candidate
        screening_result = application.screening_result

        # Собираем все в удобный словарь
        context = {
            "candidate_name": candidate.name,
            "vacancy_title": vacancy.job_title,
            "vacancy_details": {
                "required_experience": vacancy.required_experience,
                "hard_skills": vacancy.hard_skills,
                "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in
                                        vacancy.evaluation_criteria]
            },
            "screening_result": screening_result.result_json if screening_result else {}
        }
        return context

    def _initialize_history(self):
        """Задает начальный системный промпт, используя загруженный контекст."""
        # Теперь мы можем использовать self.context, который был загружен в __init__
        system_prompt_text = (
            f"Ты — HR-аватар Алекс. Ты проводишь собеседование на позицию '{self.context.get('vacancy_title')}'. "
            f"Кандидата зовут {self.context.get('candidate_name')}. "
            "Будь вежлив, задавай по одному вопросу за раз. Твоя цель - проверить компетенции кандидата."
        )
        system_prompt = {"role": "system", "content": system_prompt_text}
        self.dialogue_history.append(system_prompt)

    async def start(self) -> tuple[bytes | None, str]:
        questions_from_screening = self.context.get("screening_result", {}).get("questions_to_ask", [])

        if questions_from_screening:
            first_question = questions_from_screening[0]
            greeting_text = (
                f"Здравствуйте, {self.context.get('candidate_name')}! Меня зовут Алекс. Давайте начнем. "
                f"В вашем резюме я увидел несколько интересных моментов. {first_question}"
            )
        else:
            greeting_text = (
                f"Здравствуйте, {self.context.get('candidate_name')}! Меня зовут Алекс. "
                "Давайте начнем. Расскажите немного о себе."
            )

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
