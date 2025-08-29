from pydantic import BaseModel
from app.models.interview import InterviewStatus

class InterviewSessionStartOut(BaseModel):
    interview_session_id: int
    status: InterviewStatus