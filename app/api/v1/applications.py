import time
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.api.dependencies import get_db, get_current_user
from app.repositories.application_repository import ApplicationRepository
from app.services.resume_parser import parse_resume


# Функция для фоновой задачи
def run_resume_screening(application_id: int, db: Session):
    print(f"Запуск скрининга для заявки #{application_id}...")
    time.sleep(10)  # Имитация работы AI

    # Здесь в будущем будет реальная логика
    # А пока просто выводим в консоль
    app_repo = ApplicationRepository(db)
    # ... (здесь мог бы быть вызов get_application_by_id)

    print(f"Скрининг для заявки #{application_id} завершен!")
    # Здесь будет вызов email_service.send_screening_result(...)


router = APIRouter()


def get_current_candidate_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "CANDIDATE":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


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
