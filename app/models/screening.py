from sqlalchemy import Column, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ApplicationScreeningResult(Base):
    __tablename__ = "application_screening_results"

    id = Column(Integer, primary_key=True, index=True)
    result_json = Column(JSON, nullable=False)

    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, unique=True)

    application = relationship("Application", back_populates="screening_result")
