from sqlalchemy.orm import Session
from app.models.report import InterviewReport

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_report(self, session_id: int, analysis_data: dict) -> InterviewReport:
        db_report = InterviewReport(
            session_id=session_id,
            analysis_result=analysis_data
        )
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report