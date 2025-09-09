from pydantic import BaseModel, model_validator
from typing import Any

from .screening import ScreeningResultSummaryOut, ScreeningReportOut
from .report import InterviewReportOut
from .user import UserOut
from app.models.application import ApplicationStatus
from app.models.application import Application as ApplicationModel
from .vacancy import VacancyOut


class ApplicationCreateOut(BaseModel):
    application_id: int
    message: str


class ApplicationForCandidateOut(BaseModel):
    id: int
    status: ApplicationStatus
    vacancy: VacancyOut

    class Config:
        from_attributes = True


class ApplicationDetailsOut(BaseModel):
    id: int
    status: ApplicationStatus
    candidate: UserOut
    resume_md: str
    vacancy: VacancyOut
    interview_session_id: int | None = None
    screening_result: ScreeningReportOut | None = None
    interview_report: InterviewReportOut | None = None

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def assemble_everything(cls, data: Any) -> Any:
        if isinstance(data, ApplicationModel):
            output = data.__dict__
            if data.screening_result:
                output['screening_result'] = data.screening_result.result_json
            if data.interview_report:
                output['interview_report'] = data.interview_report
            if data.interview_session:
                output['interview_session_id'] = data.interview_session.id
            return output
        return data


class ApplicationForHROut(BaseModel):
    id: int
    status: ApplicationStatus
    job_title: str
    candidate: UserOut

    screening_match_score: int | None = None
    interview_overall_score: int | None = None
    interview_was_completed_correctly: bool | None = None
    interview_session_id: int | None = None

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def assemble_scores(cls, data: Any) -> Any:
        if isinstance(data, ApplicationModel):
            output_data = {
                "id": data.id,
                "status": data.status,
                "job_title": data.vacancy.job_title if data.vacancy else "N/A",
                "candidate": data.candidate,
                "screening_match_score": None,
                "interview_overall_score": None
            }

            if data.screening_result and data.screening_result.result_json:
                score = data.screening_result.result_json.get("overall_match_score")
                if score is not None:
                    output_data['screening_match_score'] = score

            if data.interview_session:
                output_data['interview_was_completed_correctly'] = data.interview_session.is_completed_correctly
                output_data['interview_session_id'] = data.interview_session.id

            if data.interview_report and data.interview_report.analysis_result:
                score = data.interview_report.analysis_result.get("overall_score")
                if score is not None:
                    output_data['interview_overall_score'] = score

            return output_data
        return data
