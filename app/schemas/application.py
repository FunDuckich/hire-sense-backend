from datetime import datetime
from pydantic import BaseModel
from .user import UserOut
from .vacancy import VacancyOut
from app.models.application import ApplicationStatus
from .screening import ScreeningResultSummaryOut, ScreeningReportOut


class ApplicationOut(BaseModel):
    id: int
    status: ApplicationStatus
    created_at: datetime
    candidate: UserOut
    vacancy: VacancyOut

    class Config:
        from_attributes = True


class ApplicationForHROut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut
    screening_result: ScreeningResultSummaryOut | None = None

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
