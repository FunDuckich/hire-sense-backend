from sqlalchemy.orm import Session
from app.models.screening import ApplicationScreeningResult


class ScreeningRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_screening_result(self, application_id: int, result_json: dict) -> ApplicationScreeningResult:
        db_result = ApplicationScreeningResult(
            application_id=application_id,
            result_json=result_json
        )
        self.db.add(db_result)
        self.db.commit()
        self.db.refresh(db_result)
        return db_result
