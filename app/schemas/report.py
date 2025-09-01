import enum
from typing import List
from pydantic import BaseModel, computed_field


class RecommendationEnum(str, enum.Enum):
    """Enum для строгой типизации рекомендации в отчете по интервью."""
    HIRE = "На следующий этап"
    REJECT = "Отказ"
    CLARIFY = "Требуется уточнение"


class CompetencyAnalysisOut(BaseModel):
    """Схема для оценки одной компетенции в отчете по интервью."""
    criterion: str
    score: int
    assessment: str


class InterviewReportOut(BaseModel):
    """Полная схема для структурированного отчета по результатам интервью."""
    overall_score: int
    summary: str
    recommendation: RecommendationEnum
    competency_analysis: List[CompetencyAnalysisOut]
    strengths: List[str]
    weaknesses: List[str]
    red_flags: List[str]

    class Config:
        from_attributes = True


# ====================================================================
# Схемы для отчета по результатам СКРИНИНГА РЕЗЮМЕ (из screening.py)
# ====================================================================

class CompetencyCheckOut(BaseModel):
    """Схема для проверки одной компетенции в отчете по скринингу."""
    criterion: str
    confirmed: bool
    evidence: str


class ScreeningReportOut(BaseModel):
    """Полная схема для структурированного отчета по скринингу резюме."""
    overall_match_score: int
    summary: str
    competency_check: List[CompetencyCheckOut]
    questions_to_ask: List[str]
    red_flags: List[str]

    class Config:
        from_attributes = True


class ScreeningResultSummaryOut(BaseModel):
    """Краткая схема для отображения результата скрининга в списке."""

    @computed_field
    @property
    def overall_match_score(self) -> int:
        # self здесь - это экземпляр модели ApplicationScreeningResult
        # У него есть поле result_json, которое является словарем
        if isinstance(self.result_json, dict):
            return self.result_json.get("overall_match_score", 0)
        return 0

    class Config:
        from_attributes = True
