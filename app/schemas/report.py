import enum
from typing import List
from pydantic import BaseModel


class RecommendationEnum(str, enum.Enum):
    HIRE = "На следующий этап"
    REJECT = "Отказ"
    CLARIFY = "Требуется уточнение"


class CompetencyAnalysisOut(BaseModel):
    criterion: str
    score: int
    assessment: str


class InterviewReportOut(BaseModel):
    overall_score: int
    summary: str
    recommendation: RecommendationEnum
    competency_analysis: List[CompetencyAnalysisOut]
    strengths: List[str]
    weaknesses: List[str]
    red_flags: List[str]

    class Config:
        from_attributes = True
