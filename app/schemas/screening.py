from pydantic import BaseModel
from .user import UserOut
from ..models.application import ApplicationStatus


class ScreeningResultSummaryOut(BaseModel):
    overall_match_score: int

    class Config:
        from_attributes = True


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


class ApplicationDetailsOut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut
    resume_md: str
    screening_result: ScreeningReportOut | None = None

    class Config:
        from_attributes = True
