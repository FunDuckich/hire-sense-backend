from sqlalchemy.orm import Session, joinedload
from app.models.interview import InterviewSession, InterviewStatus, InterviewTranscript, TranscriptRole
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.screening import ApplicationScreeningResult


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
        """
        Получает сессию интервью и сразу подгружает все связанные данные,
        необходимые для контекста диалога.
        """
        return self.db.query(InterviewSession).options(
            joinedload(InterviewSession.application).
            joinedload(Application.vacancy).
            joinedload(Vacancy.evaluation_criteria),
            joinedload(InterviewSession.application).
            joinedload(Application.screening_result)
        ).filter(InterviewSession.id == session_id).first()