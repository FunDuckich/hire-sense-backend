import traceback
import asyncio

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
from app.core.config import settings


def run_resume_screening(application_id: int):
    print(f"Запуск AI-скрининга для заявки #{application_id}...")

    async def _run_async():
        db: Session = SessionLocal()
        try:
            app_repo = ApplicationRepository(db)
            screening_repo = ScreeningRepository(db)
            vacancy_repo = VacancyRepository(db)
            interview_repo = InterviewRepository(db)

            application = await app_repo.get_application_by_id(application_id)
            if not application:
                print(f"Ошибка скрининга: заявка #{application_id} не найдена.")
                return

            vacancy = await vacancy_repo.get_vacancy(application.vacancy_id)
            if not vacancy:
                print(f"Ошибка скрининга: вакансия #{application.vacancy_id} не найдена.")
                return

            vacancy_details = {
                "job_title": vacancy.job_title,
                "tech_stack": vacancy.tech_stack,
                "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in
                                        vacancy.evaluation_criteria]
            }
            analysis_result = llm_service.analyze_resume(
                vacancy_details=vacancy_details,
                resume_md=application.resume_md
            )
            if not analysis_result:
                await app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
                return

            await screening_repo.create_screening_result(application_id, analysis_result)
            score = analysis_result.get("overall_match_score", 0)
            new_status = ApplicationStatus.INTERVIEW_PENDING if score >= settings.SCREENING_THRESHOLD_SCORE else ApplicationStatus.REJECTED
            updated_application = await app_repo.update_application_status(application_id, new_status)

            if updated_application:
                if new_status == ApplicationStatus.INTERVIEW_PENDING:
                    expires_at_date = datetime.now(timezone.utc) + timedelta(days=7)
                    await interview_repo.create_interview_session(
                        application_id=application.id,
                        expires_at=expires_at_date
                    )
                    email_service.send_invitation_email(updated_application)
                else:
                    email_service.send_rejection_email(updated_application)
        finally:
            await db.close()

    asyncio.run(_run_async())


def run_interview_analysis(session_id: int, is_completed_correctly: bool):
    print(f"Запуск анализа для сессии #{session_id}. Завершено корректно: {is_completed_correctly}")

    async def _run_async():
        db: AsyncSession = SessionLocal()
        try:
            report_repo = ReportRepository(db)
            existing_report = await report_repo.get_report_by_session_id(session_id)
            if existing_report:
                print(f"Отчет для сессии #{session_id} уже существует. Пропускаем.")
                return

            interview_repo = InterviewRepository(db)
            session = await interview_repo.get_session_with_details(session_id)
            if not session:
                print(f"Ошибка анализа: сессия #{session_id} не найдена.")
                return

            transcript_text = "\n".join(f"{entry.role.value}: {entry.message}" for entry in session.transcript)
            if not transcript_text.strip() and is_completed_correctly:
                print(f"Ошибка: транскрипция для сессии #{session_id} пуста.")
                return

            # === ГЛАВНОЕ ИСПРАВЛЕНИЕ ===
            analysis_result = None
            # ==========================

            if is_completed_correctly:
                print(f"Запуск полного анализа для сессии #{session_id}.")
                vacancy = session.application.vacancy
                screening_result = session.application.screening_result
                vacancy_details = {
                    "job_title": vacancy.job_title,
                    "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in
                                            vacancy.evaluation_criteria]
                }
                screening_report = screening_result.result_json if screening_result else {}
                analysis_result = llm_service.analyze_interview_transcript(
                    transcript=transcript_text,
                    vacancy_details=vacancy_details,
                    screening_report=screening_report,
                    complexity=vacancy.complexity or "Не указан"
                )
            else:
                print(f"Запуск 'дешевого' анализа для прерванной сессии #{session_id}.")
                analysis_result = llm_service.analyze_interrupted_transcript(transcript_text)

            if not analysis_result:
                print(f"Не удалось сгенерировать отчет для сессии #{session_id} (LLM вернул None).")
                analysis_result = {
                    "status_note": "Ошибка при генерации отчета AI.",
                    "summary": "Не удалось проанализировать диалог. Возможно, произошла ошибка на стороне AI-сервиса."
                }

            await report_repo.create_report(session_id=session_id, analysis_data=analysis_result)
            print(f"Анализ для сессии #{session_id} успешно завершен и сохранен.")

        except Exception as e:
            print(f"!!! КРИТИЧЕСКАЯ ОШИБКА ВНУТРИ run_interview_analysis для сессии #{session_id} !!!")
            traceback.print_exc()
        finally:
            await db.close()

    asyncio.run(_run_async())
