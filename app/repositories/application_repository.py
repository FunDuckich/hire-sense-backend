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

    def get_application_by_id(self, application_id: int) -> Application | None:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def update_application_status(self, application_id: int, status: ApplicationStatus) -> Application | None:
        db_application = self.get_application_by_id(application_id)
        if db_application:
            db_application.status = status
            self.db.add(db_application)
            self.db.commit()
            self.db.refresh(db_application)
        return db_application
