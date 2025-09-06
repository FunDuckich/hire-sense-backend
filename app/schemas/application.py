from pydantic import BaseModel, model_validator
from typing import Any

from .screening import ScreeningResultSummaryOut, ScreeningReportOut
from .report import InterviewReportOut
from .user import UserOut
from app.models.application import ApplicationStatus
from app.models.application import Application as ApplicationModel


class ApplicationDetailsOut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut
    resume_md: str

    screening_result: ScreeningReportOut | None = None
    interview_report: InterviewReportOut | None = None

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def assemble_nested_reports(cls, data: Any) -> Any:
        if not isinstance(data, ApplicationModel):
            return data

        output_data = dict(data.__dict__)

        if data.screening_result:
            output_data['screening_result'] = data.screening_result.result_json

        if hasattr(data, 'interview_report'):
            output_data['interview_report'] = data.interview_report
        elif data.interview_session and data.interview_session.report:
            output_data['interview_report'] = data.interview_session.report

        return output_data


class ApplicationForHROut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut

    screening_result: ScreeningResultSummaryOut | None = None

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def assemble_screening_summary(cls, data: Any) -> Any:
        if isinstance(data, ApplicationModel):
            output_data = dict(data.__dict__)
            if data.screening_result:
                output_data['screening_result'] = data.screening_result.result_json
            return output_data
        return data
