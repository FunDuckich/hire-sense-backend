from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone, timedelta

from app.models.interview import InterviewSession, InterviewStatus, TranscriptRole, InterviewTranscript
from app.models.application import Application, ApplicationStatus
from app.models.vacancy import Vacancy
from app.models.report import InterviewReport
from app.models.user import User


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_application_by_id(self, application_id: int) -> Application | None:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def create_interview_session(self, application_id: int, expires_at: datetime) -> InterviewSession:
        db_session = InterviewSession(
            application_id=application_id,
            status=InterviewStatus.SCHEDULED,
            expires_at=expires_at
        )
        self.db.add(db_session)
        self.db.commit()
        self.db.refresh(db_session)
        return db_session

    def add_transcript_entry(self, session_id: int, role: TranscriptRole, message: str) -> InterviewTranscript:
        db_transcript_entry = InterviewTranscript(
            session_id=session_id,
            role=role,
            message=message
        )
        self.db.add(db_transcript_entry)
        self.db.commit()
        self.db.refresh(db_transcript_entry)
        return db_transcript_entry

    def get_session_with_details(self, session_id: int) -> InterviewSession | None:
        statement = select(InterviewSession).options(
            joinedload(InterviewSession.application).options(
                joinedload(Application.candidate),
                joinedload(Application.vacancy).options(
                    joinedload(Vacancy.evaluation_criteria)
                ),
                joinedload(Application.screening_result)
            ),
            joinedload(InterviewSession.report)
        ).where(InterviewSession.id == session_id)

        return self.db.execute(statement).unique().scalar_one_or_none()

    def update_session_as_completed(self, session_id: int, is_completed_correctly: bool):
        session = self.db.get(InterviewSession, session_id)
        if session:
            session.status = InterviewStatus.COMPLETED
            session.ended_at = datetime.now(timezone.utc)
            session.is_completed_correctly = is_completed_correctly
            if session.application:
                session.application.status = ApplicationStatus.COMPLETED
            self.db.commit()
        return session

    def get_transcript_for_session(self, session_id: int) -> list[InterviewTranscript]:
        statement = select(InterviewTranscript).where(
            InterviewTranscript.session_id == session_id
        ).order_by(InterviewTranscript.timestamp.asc())

        return self.db.execute(statement).scalars().all()
