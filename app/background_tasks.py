from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.repositories.application_repository import ApplicationRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.repositories.screening_repository import ScreeningRepository
from app.services import llm_service
from app.models.application import ApplicationStatus
from app.services.email_service import email_service
from datetime import datetime, timedelta, timezone


def run_resume_screening(application_id: int):
    print(f"Запуск AI-скрининга для заявки #{application_id}...")
    db: Session = SessionLocal()
    try:
        app_repo = ApplicationRepository(db)
        screening_repo = ScreeningRepository(db)
        vacancy_repo = VacancyRepository(db)
        interview_repo = InterviewRepository(db)

        application = app_repo.get_application_by_id(application_id)
        if not application:
            print(f"Ошибка скрининга: заявка #{application_id} не найдена.")
            return

        vacancy = vacancy_repo.get_vacancy(application.vacancy_id)
        if not vacancy:
            print(f"Ошибка скрининга: вакансия #{application.vacancy_id} не найдена.")
            return

        vacancy_details = {
            "job_title": vacancy.job_title,
            "required_experience": vacancy.required_experience,
            "hard_skills": vacancy.hard_skills,
            "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in vacancy.evaluation_criteria]
        }

        analysis_result = llm_service.analyze_resume(
            vacancy_details=vacancy_details,
            resume_md=application.resume_md
        )

        if not analysis_result:
            print(f"Не удалось проанализировать резюме для заявки #{application_id}.")
            app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
            return

        screening_repo.create_screening_result(application_id, analysis_result)
        score = analysis_result.get("overall_match_score", 0)
        screening_threshold = 0
        new_status = ApplicationStatus.INTERVIEW_PENDING if score >= screening_threshold else ApplicationStatus.REJECTED

        updated_application = app_repo.update_application_status(application_id, new_status)

        if updated_application:
            if new_status == ApplicationStatus.INTERVIEW_PENDING:
                print(f"Кандидат одобрен. Создание сессии интервью со сроком годности 7 дней.")
                expires_at_date = datetime.now(timezone.utc) + timedelta(days=7)
                interview_repo.create_interview_session(
                    application_id=application.id,
                    expires_at=expires_at_date
                )
                print(f"Сессия для заявки #{application.id} создана, срок истекает {expires_at_date.isoformat()}")
                email_service.send_invitation_email(updated_application)
            else:
                email_service.send_rejection_email(updated_application)
    finally:
        db.close()


def run_interview_analysis(session_id: int, is_completed_correctly: bool):
    print(f"Запуск анализа для сессии #{session_id}. Завершено корректно: {is_completed_correctly}")
    db: Session = SessionLocal()
    try:
        interview_repo = InterviewRepository(db)
        report_repo = ReportRepository(db)

        session = interview_repo.get_session_with_details(session_id)
        if not session:
            print(f"Ошибка анализа: сессия #{session_id} не найдена.")
            return

        transcript_text = "\n".join(
            f"{entry.role.value}: {entry.message}" for entry in session.transcript
        )
        if not transcript_text and is_completed_correctly:
            print(f"Ошибка анализа: транскрипция для сессии #{session_id} пуста.")
            return

        analysis_result = None
        if is_completed_correctly:
            print(f"Запуск полного анализа для сессии #{session_id}.")
            vacancy = session.application.vacancy
            screening_result = session.application.screening_result
            vacancy_details = {
                "job_title": vacancy.job_title,
                "required_experience": vacancy.required_experience,
                "hard_skills": vacancy.hard_skills,
                "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in
                                        vacancy.evaluation_criteria]
            }
            screening_report = screening_result.result_json if screening_result else {}

            analysis_result = llm_service.analyze_interview_transcript(
                transcript=transcript_text,
                vacancy_details=vacancy_details,
                screening_report=screening_report
            )
        else:
            print(f"Запуск 'дешевого' анализа для прерванной сессии #{session_id}.")
            analysis_result = llm_service.analyze_interrupted_transcript(transcript_text)

        if not analysis_result:
            print(f"Не удалось сгенерировать отчет для сессии #{session_id}.")
            return

        report_repo.create_report(session_id=session_id, analysis_data=analysis_result)
        print(f"Анализ для сессии #{session_id} успешно завершен и сохранен.")

    finally:
        db.close()
