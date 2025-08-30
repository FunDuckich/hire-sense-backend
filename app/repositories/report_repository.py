from sqlalchemy.orm import Session
from app.models.report import InterviewReport

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_report(self, session_id: int, report_data: dict) -> InterviewReport:
        db_report = InterviewReport(
            session_id=session_id,
            overall_score=report_data.get("overall_score"),
            summary=report_data.get("summary"),
            competency_analysis=report_data.get("competency_analysis"),
            strengths=report_data.get("strengths"),
            weaknesses=report_data.get("weaknesses"),
            recommendation=report_data.get("recommendation")
        )
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report