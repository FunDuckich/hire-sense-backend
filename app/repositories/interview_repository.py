from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.interview import InterviewSession, InterviewStatus, InterviewTranscript, TranscriptRole
from app.models.application import Application
from app.models.vacancy import Vacancy


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_application_by_id(self, application_id: int) -> Application | None:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def create_interview_session(self, application_id: int) -> InterviewSession:
        db_session = InterviewSession(
            application_id=application_id,
            status=InterviewStatus.SCHEDULED
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
            )
        ).where(InterviewSession.id == session_id)

        return self.db.execute(statement).unique().scalar_one_or_none()
