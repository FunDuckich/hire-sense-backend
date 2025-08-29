import enum
from sqlalchemy import Column, Integer, Enum, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class InterviewStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class TranscriptRole(str, enum.Enum):
    AVATAR = "AVATAR"
    CANDIDATE = "CANDIDATE"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(InterviewStatus), default=InterviewStatus.SCHEDULED, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, unique=True)

    application = relationship("Application", back_populates="interview_session")
    transcript = relationship("InterviewTranscript", back_populates="session")


class InterviewTranscript(Base):
    __tablename__ = "interview_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(TranscriptRole), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)

    session = relationship("InterviewSession", back_populates="transcript")
