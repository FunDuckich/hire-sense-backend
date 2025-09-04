from pydantic import BaseModel

class InterviewReportOut(BaseModel):
    analysis_result: dict

    class Config:
        from_attributes = True