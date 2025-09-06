import asyncio
import time
from sqlalchemy.orm import Session
from app.core.config import settings
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

        self.start_time = time.time()
        self.max_duration_seconds = settings.MAX_INTERVIEW_DURATION_SECONDS

        self.context = self._load_context()
        self.dialogue_history = []
        self._initialize_history()

        self.irrelevant_answer_count = 0
        self.MAX_IRRELEVANT_ANSWERS = 2
        self.force_terminated = False

        self.is_finished_correctly = False

    def _load_context(self) -> dict:
        print(f"[Director] Loading context for session {self.session_id}")
        session_details = self.interview_repo.get_session_with_details(self.session_id)

        if not session_details:
            raise ValueError(f"Could not load context for session_id {self.session_id}")

        application = session_details.application
        vacancy = application.vacancy
        candidate = application.candidate
        screening_result = application.screening_result

        context = {
            "candidate_name": candidate.name,
            "vacancy_title": vacancy.job_title,
            "vacancy_complexity": vacancy.complexity or "Не указан",
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
        complexity = self.context.get('vacancy_complexity')
        system_prompt_text = (
            f"Ты — HR-аватар Алекс. Ты проводишь собеседование на позицию '{self.context.get('vacancy_title')}' с ожидаемым уровнем кандидата: '{complexity}'. "
            "Будь вежлив, задавай по одному вопросу за раз. Твоя цель - проверить компетенции кандидата."
        )
        self.dialogue_history.append({"role": "system", "text": system_prompt_text})

    async def _say_and_record(self, text: str, role: TranscriptRole = TranscriptRole.AVATAR) -> bytes | None:
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=role, message=text
        )
        if role == TranscriptRole.AVATAR:
            self.dialogue_history.append({"role": "assistant", "text": text})
        else:
            self.dialogue_history.append({"role": "user", "text": text})

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, tts_service.synthesize_speech, text)

    async def start(self) -> tuple[bytes | None, str]:
        questions = self.context.get("screening_result", {}).get("questions_to_ask", [])
        greeting_text = f"Здравствуйте, {self.context.get('candidate_name')}! Меня зовут Алекс. Давайте начнем."

        if questions:
            first_question = questions[0]
            full_text = f"{greeting_text} В вашем резюме я увидел несколько интересных моментов. {first_question}"
        else:
            full_text = f"{greeting_text} Расскажите немного о себе."

        audio_data = await self._say_and_record(full_text)
        return audio_data, full_text

    async def handle_candidate_response(self, text: str) -> tuple[bytes | None, str]:
        await self._say_and_record(text, role=TranscriptRole.CANDIDATE)

        loop = asyncio.get_running_loop()
        complexity = self.context.get('vacancy_complexity')

        behavior_flags = await loop.run_in_executor(
            None, llm_service.analyze_candidate_behavior, self.dialogue_history
        )

        if behavior_flags and behavior_flags.get("is_toxic"):
            return await self._terminate_for_behavior("toxic")

        if behavior_flags and behavior_flags.get("is_off_topic"):
            self.irrelevant_answer_count += 1
            if self.irrelevant_answer_count >= self.MAX_IRRELEVANT_ANSWERS:
                return await self._terminate_for_behavior("off_topic")
            else:
                last_question = self.dialogue_history[-2].get("text", "")
                return await self._guide_back_to_question(last_question)

        self.irrelevant_answer_count = 0

        if time.time() - self.start_time > self.max_duration_seconds:
            return await self._get_final_phrase()

        completion_status = await loop.run_in_executor(
            None,
            llm_service.check_interview_completion,
            self.dialogue_history,
            self.context.get("vacancy_details", {}),
            complexity
        )

        if completion_status == "FINISH":
            return await self._get_final_phrase()

        next_question = await loop.run_in_executor(
            None,
            llm_service.get_interview_response,
            self.dialogue_history,
            self.context.get("vacancy_details", {}),
            self.context.get("screening_result", {}),
            complexity
        )

        audio_data = await self._say_and_record(next_question)
        return audio_data, next_question

    async def _get_final_phrase(self) -> tuple[bytes | None, str]:
        self.is_finished_correctly = True
        final_text = f"Спасибо, {self.context.get('candidate_name')}. На этом у меня все вопросы. Всего доброго!"
        audio_data = await self._say_and_record(final_text)
        return audio_data, final_text

    async def _guide_back_to_question(self, last_question: str) -> tuple[bytes | None, str]:
        text_to_say = f"Я понимаю, но давайте, пожалуйста, вернемся к последнему вопросу: {last_question}"
        audio_data = await self._say_and_record(text_to_say)
        return audio_data, text_to_say

    async def _terminate_for_behavior(self, reason: str) -> tuple[bytes | None, str]:
        text_to_say = "Я вынужден прервать интервью из-за использования недопустимой лексики. Всего доброго." \
            if reason == "toxic" else \
            "К сожалению, мы не можем продолжить, так как не удается получить ответы на заданные вопросы. Интервью завершено."

        self.force_terminated = True
        audio_data = await self._say_and_record(text_to_say)
        return audio_data, text_to_say
