from typing import List

from pydantic import BaseModel


class InterviewReportOut(BaseModel):
    analysis_result: dict

    class Config:
        from_attributes = True


class CandidateFeedbackOut(BaseModel):
    positive_points: List[str] = []
    areas_for_growth: List[str] = []
