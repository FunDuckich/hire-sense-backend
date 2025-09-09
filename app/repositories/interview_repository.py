from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.models.interview import InterviewSession, InterviewStatus, TranscriptRole, InterviewTranscript
from app.models.application import Application
from app.models.vacancy import Vacancy


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_interview_session(self, application_id: int, expires_at: datetime) -> InterviewSession:
        db_session = InterviewSession(
            application_id=application_id,
            status=InterviewStatus.SCHEDULED,
            expires_at=expires_at
        )
        self.db.add(db_session)
        await self.db.commit()
        await self.db.refresh(db_session)
        return db_session

    async def add_transcript_entry(self, session_id: int, role: TranscriptRole, message: str) -> InterviewTranscript:
        db_transcript_entry = InterviewTranscript(
            session_id=session_id,
            role=role,
            message=message
        )
        self.db.add(db_transcript_entry)
        await self.db.commit()
        await self.db.refresh(db_transcript_entry)
        return db_transcript_entry

    async def get_session_with_details(self, session_id: int) -> InterviewSession | None:
        statement = select(InterviewSession).options(
            joinedload(InterviewSession.application).options(
                joinedload(Application.candidate),
                joinedload(Application.vacancy).options(
                    joinedload(Vacancy.evaluation_criteria)
                ),
                joinedload(Application.screening_result)
            ),
            joinedload(InterviewSession.report),
            joinedload(InterviewSession.transcript)
        ).where(InterviewSession.id == session_id)

        result = await self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    async def update_session_completion_status(self, session_id: int, is_completed_correctly: bool):
        session = await self.db.get(InterviewSession, session_id)
        if session:
            session.is_completed_correctly = is_completed_correctly
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
        return session

    async def update_session_as_completed(self, session_id: int, is_completed_correctly: bool):
        from app.models.application import ApplicationStatus
        session = await self.db.get(InterviewSession, session_id, options=[joinedload(InterviewSession.application)])
        if session:
            session.status = InterviewStatus.COMPLETED
            session.ended_at = datetime.now()
            session.is_completed_correctly = is_completed_correctly
            if session.application:
                session.application.status = ApplicationStatus.COMPLETED
            await self.db.commit()
        return session

    async def get_transcript_for_session(self, session_id: int) -> list[InterviewTranscript]:
        statement = select(InterviewTranscript).where(
            InterviewTranscript.session_id == session_id
        ).order_by(InterviewTranscript.timestamp.asc())
        result = await self.db.execute(statement)
        return result.scalars().all()