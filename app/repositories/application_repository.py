from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.models.application import Application, ApplicationStatus
from app.models.interview import InterviewSession

class ApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_application(self, user_id: int, vacancy_id: int, resume_md: str) -> Application:
        db_application = Application(
            user_id=user_id,
            vacancy_id=vacancy_id,
            resume_md=resume_md,
            status=ApplicationStatus.SCREENING
        )
        self.db.add(db_application)
        await self.db.commit()
        await self.db.refresh(db_application)
        return db_application

    async def get_application_by_id(self, application_id: int) -> Application | None:
        statement = select(Application).options(
            joinedload(Application.candidate),
            joinedload(Application.vacancy),
            joinedload(Application.screening_result),
            joinedload(Application.interview_session).joinedload(InterviewSession.report)
        ).where(Application.id == application_id)
        result = await self.db.execute(statement)
        return result.unique().scalar_one_or_none()
        
    async def get_application_with_report(self, application_id: int) -> Application | None:
        statement = select(Application).options(
            joinedload(Application.interview_session).joinedload(InterviewSession.report)
        ).where(Application.id == application_id)
        result = await self.db.execute(statement)
        return result.unique().scalar_one_or_none()

    async def update_application_status(self, application_id: int, status: ApplicationStatus) -> Application | None:
        db_application = await self.db.get(Application, application_id)
        if db_application:
            db_application.status = status
            await self.db.commit()
            await self.db.refresh(db_application)
        return db_application

    async def get_applications_for_vacancy(self, vacancy_id: int) -> list[Application]:
        statement = select(Application).options(
            joinedload(Application.candidate),
            joinedload(Application.screening_result),
            joinedload(Application.interview_session).joinedload(InterviewSession.report)
        ).where(Application.vacancy_id == vacancy_id)
        result = await self.db.execute(statement)
        return result.unique().scalars().all()

    async def get_applications_for_user(self, user_id: int) -> list[Application]:
        statement = select(Application).options(
            joinedload(Application.vacancy)
        ).where(Application.user_id == user_id).order_by(Application.created_at.desc())
        result = await self.db.execute(statement)
        return result.unique().scalars().all()