from sqlalchemy.orm import Session
from app.models.report import InterviewReport


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_report(
            self,
            session_id: int,
            final_summary: dict,
            speech_sense_summary: dict | None = None
    ) -> InterviewReport:
        db_report = InterviewReport(
            session_id=session_id,
            final_summary_result=final_summary,
            speech_sense_result=speech_sense_summary
        )
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report
