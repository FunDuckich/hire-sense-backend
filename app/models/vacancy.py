from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String, index=True, nullable=False)
    company_name = Column(String)
    location = Column(String)
    salary_range = Column(String)
    key_responsibilities = Column(Text)
    tech_stack = Column(Text)
    required_experience = Column(Text)
    hard_skills = Column(Text)
    soft_skills = Column(Text)
    education = Column(String)
    what_we_offer = Column(Text)

    evaluation_criteria = relationship("EvaluationCriterion", back_populates="vacancy")


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    id = Column(Integer, primary_key=True, index=True)
    criterion = Column(String, nullable=False)
    weight = Column(Integer, nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)

    # Связь "многие к одному" с вакансией
    vacancy = relationship("Vacancy", back_populates="evaluation_criteria")
