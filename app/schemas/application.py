from pydantic import BaseModel
from .screening import ScreeningResultSummaryOut, ScreeningReportOut
from .report import InterviewReportOut
from .user import UserOut
from app.models.application import ApplicationStatus


class ApplicationDetailsOut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut
    resume_md: str
    screening_result: ScreeningReportOut | None = None

    interview_report: InterviewReportOut | None = None

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
