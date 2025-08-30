from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id = Column(Integer, primary_key=True, index=True)
    overall_score = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)
    competency_analysis = Column(JSON, nullable=False)
    strengths = Column(JSON)
    weaknesses = Column(JSON)
    recommendation = Column(String, nullable=False)

    session_id = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False, unique=True)

    session = relationship("InterviewSession", back_populates="report")