from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.api.dependencies import get_db, get_current_user
from app.repositories.application_repository import ApplicationRepository
from app.services.resume_parser import parse_resume
from app.repositories.vacancy_repository import VacancyRepository
from app.repositories.screening_repository import ScreeningRepository
from app.services import llm_service
from app.models.application import ApplicationStatus
from app.api.dependencies import get_current_hr_user
from app.schemas.application import ApplicationForHROut, ApplicationDetailsOut


# фоновая задача
def run_resume_screening(application_id: int, db: Session):
    print(f"Запуск AI-скрининга для заявки #{application_id}...")

    app_repo = ApplicationRepository(db)
    screening_repo = ScreeningRepository(db)
    vacancy_repo = VacancyRepository(db)

    application = app_repo.get_application_by_id(application_id)
    if not application:
        print(f"Ошибка: заявка #{application_id} не найдена.")
        return

    vacancy = vacancy_repo.get_vacancy(application.vacancy_id)
    if not vacancy:
        print(f"Ошибка: вакансия #{application.vacancy_id} не найдена.")
        return

    vacancy_details = {
        "job_title": vacancy.job_title,
        "required_experience": vacancy.required_experience,
        "hard_skills": vacancy.hard_skills,
        "evaluation_criteria": [{"criterion": c.criterion, "weight": c.weight} for c in vacancy.evaluation_criteria]
    }

    analysis_result = llm_service.analyze_resume(
        vacancy_details=vacancy_details,
        resume_md=application.resume_md
    )

    if not analysis_result:
        print(f"Ошибка: не удалось проанализировать резюме для заявки #{application_id}.")
        app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
        return

    screening_repo.create_screening_result(application_id, analysis_result)

    score = analysis_result.get("overall_match_score", 0)
    screening_threshold = 60  # пока хардкодим, потом можно будет брать из вакансии

    new_status = ApplicationStatus.INTERVIEW_PENDING if score >= screening_threshold else ApplicationStatus.REJECTED
    app_repo.update_application_status(application_id, new_status)

    # 5. TODO: Отправить email-уведомление кандидату
    print(f"Скрининг для заявки #{application_id} завершен! Результат: {score}%, Статус: {new_status.value}")


router = APIRouter()


def get_current_candidate_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "CANDIDATE":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


@router.get("/vacancies/{vacancy_id}/applications", response_model=List[ApplicationForHROut])
def read_applications_for_vacancy(
        vacancy_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    vacancy_repo = VacancyRepository(db)
    vacancy = vacancy_repo.get_vacancy(vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    if vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access applications for this vacancy")

    app_repo = ApplicationRepository(db)
    return app_repo.get_applications_for_vacancy(vacancy_id=vacancy_id)


@router.post("/vacancies/{vacancy_id}/apply", status_code=status.HTTP_202_ACCEPTED)
async def apply_for_vacancy(
        vacancy_id: int,
        background_tasks: BackgroundTasks,
        resume_file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    resume_md = await parse_resume(resume_file)

    app_repo = ApplicationRepository(db)
    application = app_repo.create_application(
        user_id=current_user.id,
        vacancy_id=vacancy_id,
        resume_md=resume_md
    )

    background_tasks.add_task(run_resume_screening, application.id, db)

    return {"message": "Your application has been accepted and is being processed."}


@router.get("/applications/{application_id}", response_model=ApplicationDetailsOut)
def read_application_details(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    app_repo = ApplicationRepository(db)
    application = app_repo.get_application_by_id(application_id=application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this application")

    if application.screening_result:
        application.screening_result = application.screening_result.result_json

    return application
