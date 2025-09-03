import enum
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from app.core.database import Base


class VacancyTagType(str, enum.Enum):
    HARD_SKILL = "HARD_SKILL"
    SOFT_SKILL = "SOFT_SKILL"
    TOOL = "TOOL"
    UNIVERSAL_INCONFIDENCE = "UNIVERSAL_INCONFIDENCE"
    UNIVERSAL_NEGATIVITY = "UNIVERSAL_NEGATIVITY"
    UNIVERSAL_ACHIEVEMENT = "UNIVERSAL_ACHIEVEMENT"


class VacancyTag(Base):
    __tablename__ = "vacancy_tags"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    type = Column(SQLAlchemyEnum(VacancyTagType), nullable=False)
    is_custom = Column(Boolean, default=False)

    speech_sense_dict_id = Column(String, nullable=True, unique=True)

    vacancy_id = Column(Integer, ForeignKey("vacancies.id"), nullable=False)
    vacancy = relationship("Vacancy", back_populates="tags")