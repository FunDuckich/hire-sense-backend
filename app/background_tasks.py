from sqlalchemy.orm import Session
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository
from app.services import llm_service
from app.core.database import SessionLocal


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