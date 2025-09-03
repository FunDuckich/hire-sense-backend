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


def run_resume_screening(application_id: int):
    """
    Фоновая задача для AI-скрининга резюме.
    Создает собственную сессию БД.
    """
    print(f"Запуск AI-скрининга для заявки #{application_id}...")

    db = SessionLocal()
    try:
        # Вся остальная логика остается почти без изменений
        app_repo = ApplicationRepository(db)
        screening_repo = ScreeningRepository(db)
        vacancy_repo = VacancyRepository(db)

        application = app_repo.get_application_by_id(application_id)
        if not application:
            print(f"Ошибка: заявка #{application_id} не найдена.")
            return

        vacancy = vacancy_repo.get_vacancy(application.vacancy_id)
        if not vacancy:
            print(f"Ошибка: вакансия #{application.vacancy_id} не найдена.")
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
            print(f"Ошибка: не удалось проанализировать резюме для заявки #{application_id}.")
            app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
            return

        screening_repo.create_screening_result(application_id, analysis_result)

        score = analysis_result.get("overall_match_score", 0)
        screening_threshold = 60

        new_status = ApplicationStatus.INTERVIEW_PENDING if score >= screening_threshold else ApplicationStatus.REJECTED
        updated_application = app_repo.update_application_status(application_id, new_status)

        print(f"Скрининг для заявки #{application_id} завершен! Результат: {score}%, Статус: {new_status.value}")

        if updated_application:
            if new_status == ApplicationStatus.INTERVIEW_PENDING:
                email_service.send_invitation_email(updated_application)
            else:
                email_service.send_rejection_email(updated_application)

    finally:
        db.close()
        print(f"Сессия БД для задачи скрининга заявки #{application_id} закрыта.")

def run_interview_analysis(session_id: int):
    print(f"Запуск финального анализа для сессии интервью #{session_id}...")

    db: Session = SessionLocal()

    try:
        interview_repo = InterviewRepository(db)
        report_repo = ReportRepository(db)

        session_details = interview_repo.get_session_with_details(session_id)
        if not session_details:
            print(f"Ошибка анализа: сессия #{session_id} не найдена.")
            return

        transcript_entries = session_details.transcript
        transcript_text = "\n".join(
            f"{entry.role.value}: {entry.message}" for entry in transcript_entries
        )
        if not transcript_text:
            print(f"Ошибка анализа: транскрипция для сессии #{session_id} пуста.")
            return

        application = session_details.application
        vacancy = application.vacancy
        screening_result = application.screening_result

        vacancy_details = {
            "job_title": vacancy.job_title,
            "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in vacancy.evaluation_criteria]
        }
        screening_report = screening_result.result_json if screening_result else {}

        analysis_result = llm_service.analyze_interview_transcript(
            transcript=transcript_text,
            vacancy_details=vacancy_details,
            screening_report=screening_report
        )

        if not analysis_result:
            print(f"Ошибка: не удалось сгенерировать отчет для сессии #{session_id}.")
            return

        report_repo.create_report(session_id=session_id, report_data=analysis_result)

        print(f"Финальный анализ для сессии #{session_id} успешно завершен и сохранен.")

    finally:
        db.close()


def run_resume_screening(application_id: int, db: Session):
    print(f"Запуск AI-скрининга для заявки #{application_id}...")

    app_repo = ApplicationRepository(db)
    screening_repo = ScreeningRepository(db)
    vacancy_repo = VacancyRepository(db)

    application = app_repo.get_application_by_id(application_id)
    if not application:
        print(f"Ошибка: заявка #{application_id} не найдена.")
        return

    vacancy = vacancy_repo.get_vacancy(application.vacancy_id)
    if not vacancy:
        print(f"Ошибка: вакансия #{application.vacancy_id} не найдена.")
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
        print(f"Ошибка: не удалось проанализировать резюме для заявки #{application_id}.")
        app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
        return

    screening_repo.create_screening_result(application_id, analysis_result)

    score = analysis_result.get("overall_match_score", 0)
    screening_threshold = 60

    new_status = ApplicationStatus.INTERVIEW_PENDING if score >= screening_threshold else ApplicationStatus.REJECTED
    updated_application = app_repo.update_application_status(application_id, new_status)

    print(f"Скрининг для заявки #{application_id} завершен! Результат: {score}%, Статус: {new_status.value}")

    if updated_application:
        if new_status == ApplicationStatus.INTERVIEW_PENDING:
            email_service.send_invitation_email(updated_application)
        else:
            email_service.send_rejection_email(updated_application)