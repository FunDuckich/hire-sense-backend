import enum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base


class VacancyStatus(str, enum.Enum):
    DRAFT = "DRAFT" # Создана вручную, ожидает заполнения
    PARSING = "PARSING" # Загружен PDF, идет парсинг полей
    PREPARING_TAGS = "PREPARING_TAGS" # Поля заполнены, идет генерация тегов
    PENDING_REVIEW = "PENDING_REVIEW" # Все готово, ждет проверки HR
    PUBLISHED = "PUBLISHED" # Опубликована и видна кандидатам
    ARCHIVED = "ARCHIVED" # В архиве, не видна кандидатам


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
    status = Column(Enum(VacancyStatus), nullable=False, default=VacancyStatus.DRAFT)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="vacancies")
    tags = relationship("VacancyTag", back_populates="vacancy", cascade="all, delete-orphan")
    evaluation_criteria = relationship("EvaluationCriterion", back_populates="vacancy", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="vacancy", cascade="all, delete-orphan")


class EvaluationCriterion(Base):
    __tablename__ = "evaluation_criteria"

    id = Column(Integer, primary_key=True, index=True)
    criterion = Column(String, nullable=False)
    weight = Column(Integer, nullable=False)
    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)

    vacancy = relationship("Vacancy", back_populates="evaluation_criteria")
