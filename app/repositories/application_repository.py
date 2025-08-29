from sqlalchemy.orm import Session
from app.models.application import Application, ApplicationStatus


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_application(self, user_id: int, vacancy_id: int, resume_md: str) -> Application:
        db_application = Application(
            user_id=user_id,
            vacancy_id=vacancy_id,
            resume_md=resume_md,
            status=ApplicationStatus.SCREENING
        )
        self.db.add(db_application)
        self.db.commit()
        self.db.refresh(db_application)
        return db_application
