from pydantic import BaseModel

class InterviewReportOut(BaseModel):
    speech_sense_result: dict | None = None
    final_summary_result: dict

    class Config:
        from_attributes = True