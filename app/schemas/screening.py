from pydantic import BaseModel, computed_field

# Схема для CompetencyCheck в отчете
class CompetencyCheckOut(BaseModel):
    criterion: str
    confirmed: bool
    evidence: str

# Схема для полного отчета по скринингу
class ScreeningReportOut(BaseModel):
    overall_match_score: int
    summary: str
    competency_check: list[CompetencyCheckOut]
    questions_to_ask: list[str]
    red_flags: list[str]

    class Config:
        from_attributes = True

# Схема для краткого вывода в списке (воронке HR)
class ScreeningResultSummaryOut(BaseModel):
    @computed_field
    @property
    def overall_match_score(self) -> int:
        if isinstance(self.result_json, dict):
            return self.result_json.get("overall_match_score", 0)
        return 0

    class Config:
        from_attributes = True

# --- ApplicationDetailsOut ЗДЕСЬ БОЛЬШЕ НЕТ ---