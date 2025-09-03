from pydantic import BaseModel, computed_field


class CompetencyCheckOut(BaseModel):
    criterion: str
    confirmed: bool
    evidence: str


class ScreeningReportOut(BaseModel):
    overall_match_score: int
    summary: str
    competency_check: list[CompetencyCheckOut]
    questions_to_ask: list[str]
    red_flags: list[str]

    class Config:
        from_attributes = True


class ScreeningResultSummaryOut(BaseModel):
    overall_match_score: int

    class Config:
        from_attributes = True
