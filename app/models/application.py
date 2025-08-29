import enum
from sqlalchemy import Column, Integer, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ApplicationStatus(str, enum.Enum):
    SCREENING = "SCREENING"
    INTERVIEW_PENDING = "INTERVIEW_PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.SCREENING, nullable=False)
    resume_md = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)

    # Связи
    candidate = relationship("User", back_populates="applications")
    vacancy = relationship("Vacancy", back_populates="applications")
    interview_session = relationship("InterviewSession", uselist=False, back_populates="application")
