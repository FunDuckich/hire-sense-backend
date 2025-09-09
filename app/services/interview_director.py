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
        self.silence_count = 0
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
        full_text = llm_service.generate_greeting_phrase(
            candidate_name=self.context.get('candidate_name'),
            vacancy_title=self.context.get('vacancy_title'),
            first_question=self.context.get("screening_result", {}).get("questions_to_ask", [None])[0]
        )

        self._record_message(full_text, TranscriptRole.AVATAR)
        return full_text

    def handle_candidate_response(self, text: str) -> str:
        self.silence_count = 0
        self._record_message(text, TranscriptRole.CANDIDATE)

        behavior_flags = llm_service.analyze_candidate_behavior(self.dialogue_history)

        if behavior_flags and (behavior_flags.get("is_toxic") or behavior_flags.get("wants_to_finish")):
            return self._terminate_for_behavior("toxic") if behavior_flags.get("is_toxic") else self._get_final_phrase()

        if behavior_flags and behavior_flags.get("is_off_topic"):
            self.irrelevant_answer_count += 1
            if self.irrelevant_answer_count >= settings.MAX_IRRELEVANT_ANSWERS:
                return self._terminate_for_behavior("off_topic")
        else:
            self.irrelevant_answer_count = 0

        if time.time() - self.start_time > self.max_duration_seconds:
            return self._get_final_phrase(reason='time_limit')

        completion_status = llm_service.check_interview_completion(
            self.dialogue_history,
            self.context.get("vacancy_details", {}),
            self.context.get("vacancy_complexity")
        )
        if completion_status == "FINISH":
            return self._get_final_phrase()

        last_question = next((msg['text'] for msg in reversed(self.dialogue_history) if msg['role'] == 'assistant'), "")
        depth_analysis = llm_service.evaluate_answer_depth(
            question=last_question,
            answer=text
        )

        next_question = llm_service.get_interview_response(
            history=self.dialogue_history,
            vacancy_details=self.context.get("vacancy_details", {}),
            last_answer_analysis=depth_analysis,
            behavior_flags=behavior_flags
        )

        self._record_message(next_question, TranscriptRole.AVATAR)
        return next_question

    def handle_candidate_silence(self) -> str:
        self.silence_count += 1
        print(f"[Director] Silence count incremented to: {self.silence_count}")
        if self.silence_count >= settings.MAX_SILENCE_PROMPTS:
            self.force_terminated = True
            text_to_say = "Похоже, у нас возникли проблемы со связью. Я вынужден завершить интервью. Всего доброго."
            self._record_message(text_to_say, TranscriptRole.AVATAR)
            return text_to_say
        else:
            print("[Director] Generating support phrase.")
            text_to_say = llm_service.generate_support_phrase(self.dialogue_history)
            self._record_message(text_to_say, TranscriptRole.AVATAR)
            return text_to_say

    def finalize_session(self):
        print(f"Finalizing session {self.session_id} with correct completion: {self.is_finished_correctly}")
        self.interview_repo.update_session_as_completed(
            session_id=self.session_id,
            is_completed_correctly=self.is_finished_correctly
        )

    def _get_final_phrase(self, reason: str = 'normal') -> str:
        self.is_finished_correctly = True
        final_text = llm_service.generate_closing_phrase(
            candidate_name=self.context.get('candidate_name'),
            dialogue_history=self.dialogue_history,
            reason=reason
        )
        self.is_finished_correctly = True
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
        self.is_finished_correctly = True
        self.force_terminated = True
        self._record_message(text_to_say, TranscriptRole.AVATAR)
        return text_to_say
