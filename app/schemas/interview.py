from pydantic import BaseModel
from app.models.interview import InterviewStatus, TranscriptRole
from datetime import datetime


class InterviewSessionStartOut(BaseModel):
    interview_session_id: int
    status: InterviewStatus

class TranscriptEntryOut(BaseModel):
    role: TranscriptRole
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class InterviewTranscriptOut(BaseModel):
    session_id: int
    entries: list[TranscriptEntryOut]