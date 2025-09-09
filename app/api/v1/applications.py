from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, Role
from app.api.dependencies import get_db, get_current_user, get_current_candidate_user, get_current_hr_user
from app.repositories.application_repository import ApplicationRepository
from app.services.file_parser import parse_file
from app.schemas.application import ApplicationDetailsOut, ApplicationCreateOut, ApplicationForCandidateOut
from app.background_tasks import run_resume_screening

router = APIRouter()

@router.post("/vacancies/{vacancy_id}/apply", response_model=ApplicationCreateOut, status_code=status.HTTP_202_ACCEPTED)
async def apply_for_vacancy(
        vacancy_id: int,
        background_tasks: BackgroundTasks,
        resume_file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    resume_md = await parse_file(resume_file)
    app_repo = ApplicationRepository(db)
    application = await app_repo.create_application(
        user_id=current_user.id,
        vacancy_id=vacancy_id,
        resume_md=resume_md
    )
    background_tasks.add_task(run_resume_screening, application.id)
    return {"application_id": application.id, "message": "Your application has been accepted and is being processed."}

@router.get("/applications/{application_id}", response_model=ApplicationDetailsOut)
async def read_application_details(
        application_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    app_repo = ApplicationRepository(db)
    application = await app_repo.get_application_by_id(application_id=application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")
    return application

@router.get("/applications/my", response_model=List[ApplicationForCandidateOut])
async def read_my_applications(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role == Role.HR:
        raise HTTPException(status_code=403, detail="This endpoint is for candidates only.")
    app_repo = ApplicationRepository(db)
    applications = await app_repo.get_applications_for_user(user_id=current_user.id)
    return applications