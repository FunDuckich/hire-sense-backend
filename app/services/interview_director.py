import time
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.interview import TranscriptRole
from app.repositories.interview_repository import InterviewRepository
from app.services import llm_service


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
        self.MAX_IRRELEVANT_ANSWERS = settings.MAX_IRRELEVANT_ANSWERS

        self.force_terminated = False
        self.is_finished_correctly = False

    def _load_context(self) -> dict:
        session_details = self.interview_repo.get_session_with_details(self.session_id)
        if not session_details:
            raise ValueError(f"Could not load context for session_id {self.session_id}")

        application = session_details.application
        vacancy = application.vacancy
        candidate = application.candidate
        screening_result = application.screening_result

        return {
            "candidate_name": candidate.name,
            "vacancy_title": vacancy.job_title,
            "vacancy_complexity": vacancy.complexity or "Не указан",
            "vacancy_details": {
                "required_experience": vacancy.required_experience,
                "hard_skills": vacancy.hard_skills,
                "tech_stack": vacancy.tech_stack,
                "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in
                                        vacancy.evaluation_criteria]
            },
            "screening_result": screening_result.result_json if screening_result else {}
        }

    def _initialize_history(self):
        complexity = self.context.get('vacancy_complexity')
        system_prompt = (
            f"Ты — HR-аватар Алекс. Ты проводишь собеседование на позицию '{self.context.get('vacancy_title')}' с ожидаемым уровнем кандидата: '{complexity}'. "
            "Будь вежлив, задавай по одному вопросу за раз. Твоя цель - проверить компетенции кандидата."
        )
        self.dialogue_history.append({"role": "system", "text": system_prompt})

    def _record_message(self, text: str, role: TranscriptRole):
        self.interview_repo.add_transcript_entry(
            session_id=self.session_id, role=role, message=text
        )
        role_str = "assistant" if role == TranscriptRole.AVATAR else "user"
        self.dialogue_history.append({"role": role_str, "text": text})

    def start(self) -> str:
        questions = self.context.get("screening_result", {}).get("questions_to_ask", [])
        greeting_text = f"Здравствуйте, {self.context.get('candidate_name')}! Меня зовут Алекс. Давайте начнем."

        if questions:
            first_question = questions[0]
            full_text = f"{greeting_text} В вашем резюме я увидел несколько интересных моментов. {first_question}"
        else:
            full_text = f"{greeting_text} Расскажите немного о себе."

        self._record_message(full_text, TranscriptRole.AVATAR)
        return full_text

    def handle_candidate_response(self, text: str) -> str:
        self._record_message(text, TranscriptRole.CANDIDATE)

        complexity = self.context.get('vacancy_complexity')

        behavior_flags = llm_service.analyze_candidate_behavior(self.dialogue_history)

        if behavior_flags and behavior_flags.get("is_toxic"):
            return self._terminate_for_behavior("toxic")

        if behavior_flags and behavior_flags.get("is_off_topic"):
            self.irrelevant_answer_count += 1
            if self.irrelevant_answer_count >= self.MAX_IRRELEVANT_ANSWERS:
                return self._terminate_for_behavior("off_topic")
            else:
                last_question = self.dialogue_history[-2].get("text", "")
                return self._guide_back_to_question(last_question)

        self.irrelevant_answer_count = 0

        if time.time() - self.start_time > self.max_duration_seconds:
            return self._get_final_phrase()

        if time.time() - self.start_time > self.max_duration_seconds:
            return self._get_final_phrase(reason='time_limit')

        completion_status = llm_service.check_interview_completion(
            self.dialogue_history,
            self.context.get("vacancy_details", {}),
            complexity
        )
        if completion_status == "FINISH":
            return self._get_final_phrase()

        next_question = llm_service.get_interview_response(
            history=self.dialogue_history,
            vacancy_details=self.context.get("vacancy_details", {}),
            resume_summary=self.context.get("screening_result", {}),
            complexity=complexity
        )

        self._record_message(next_question, TranscriptRole.AVATAR)
        return next_question

    def _get_final_phrase(self, reason: str = 'normal') -> str:
        self.is_finished_correctly = True
        final_text = llm_service.generate_closing_phrase(
            candidate_name=self.context.get('candidate_name'),
            dialogue_history=self.dialogue_history,
            reason=reason
        )
        self._record_message(final_text, TranscriptRole.AVATAR)
        return final_text

    def _guide_back_to_question(self, last_question: str) -> str:
        text_to_say = f"Я понимаю, но давайте, пожалуйста, вернемся к последнему вопросу: {last_question}"
        self._record_message(text_to_say, TranscriptRole.AVATAR)
        return text_to_say

    def _terminate_for_behavior(self, reason: str) -> str:
        if reason == "toxic":
            text_to_say = "Я вынужден прервать интервью из-за использования недопустимой лексики. Всего доброго."
        elif reason == "off_topic":
            last_question = self.dialogue_history[-2].get("text", "")
            text_to_say = llm_service.generate_moderation_phrase(
                reason='final_warning',
                last_question=last_question
            )
        else:
            text_to_say = "По техническим причинам интервью завершено."

        self.force_terminated = True
        self._record_message(text_to_say, TranscriptRole.AVATAR)
        return text_to_say