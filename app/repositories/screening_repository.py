from sqlalchemy.orm import Session
from app.models.screening import ApplicationScreeningResult


class ScreeningRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create_screening_result(self, application_id: int, result_data: dict) -> ApplicationScreeningResult:
        db_screening_result = ApplicationScreeningResult(
            application_id=application_id,
            result_json=result_data
        )
        self.db.add(db_screening_result)
        await self.db.commit()
        await self.db.refresh(db_screening_result)
        return db_screening_result