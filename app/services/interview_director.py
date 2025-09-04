import asyncio

from sqlalchemy.orm import Session, joinedload
from app.models.interview import TranscriptRole, InterviewStatus
from app.repositories.interview_repository import InterviewRepository
from app.services import tts_service, llm_service

import time
from app.core.config import settings


class InterviewDirector:
    def __init__(self, session_id: int, db: Session):
        if not session_id:
            raise ValueError("session_id must be provided")

        self.session_id = session_id
        self.db = db
        self.interview_repo = InterviewRepository(db)
        self.llm_service = llm_service
        self.dialogue_history = []

        self.start_time = time.time()
        self.max_duration_seconds = settings.MAX_INTERVIEW_DURATION_SECONDS

        self.context = self._load_context()

        self._initialize_history()
        self.is_finished_correctly = False

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

        loop = asyncio.get_running_loop()

        if time.time() - self.start_time > self.max_duration_seconds:
            print(f"[Director] Превышен лимит времени ({self.max_duration_seconds} сек). Завершение интервью.")
            return await self._get_final_phrase()

        completion_status = await loop.run_in_executor(
            None,
            llm_service.check_interview_completion,
            self.dialogue_history,
            self.context.get("vacancy_details", {})
        )

        if completion_status == "FINISH":
            print("[Director] LLM решила, что вся информация собрана. Завершение интервью.")
            return await self._get_final_phrase()

        print("[Director] Интервью продолжается. Генерация следующего вопроса...")
        next_question = await loop.run_in_executor(
            None,
            llm_service.get_interview_response,
            self.dialogue_history,
            self.context.get("vacancy_details", {}),
            self.context.get("screening_result", {})
        )

        print(f"[Director] Ответ LLM: '{next_question}'")

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=next_question
        )
        self.dialogue_history.append({"role": "assistant", "content": next_question})

        audio_data = await loop.run_in_executor(None, tts_service.synthesize_speech, next_question)

        return audio_data, next_question

    async def _get_final_phrase(self) -> tuple[bytes | None, str]:
        self.is_finished_correctly = True
        final_text = (
            f"Спасибо, {self.context.get('candidate_name')}. На этом у меня все вопросы закончились. "
            "Мы свяжемся с вами в ближайшее время. Всего доброго!"
        )

        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=TranscriptRole.AVATAR, message=final_text
        )
        self.dialogue_history.append({"role": "assistant", "content": final_text})

        loop = asyncio.get_running_loop()
        audio_data = await loop.run_in_executor(None, tts_service.synthesize_speech, final_text)

        return audio_data, final_text
