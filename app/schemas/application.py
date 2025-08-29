from datetime import datetime
from pydantic import BaseModel
from .user import UserOut
from .vacancy import VacancyOut
from app.models.application import ApplicationStatus


class ApplicationOut(BaseModel):
    id: int
    status: ApplicationStatus
    created_at: datetime
    candidate: UserOut
    vacancy: VacancyOut

    class Config:
        from_attributes = True
