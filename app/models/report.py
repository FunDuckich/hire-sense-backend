from sqlalchemy import Column, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id = Column(Integer, primary_key=True, index=True)

    analysis_result = Column(JSON, nullable=False)

    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, unique=True)
    session = relationship("InterviewSession", back_populates="report")