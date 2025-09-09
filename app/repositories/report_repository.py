from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.report import InterviewReport


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    async def get_report_by_session_id(self, session_id: int) -> InterviewReport | None:
        statement = select(InterviewReport).where(InterviewReport.session_id == session_id)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def create_report(self, session_id: int, analysis_data: dict) -> InterviewReport:
        db_report = InterviewReport(
            session_id=session_id,
            analysis_result=analysis_data
        )
        self.db.add(db_report)
        await self.db.commit()
        await self.db.refresh(db_report)
        return db_report