from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_hr_user
from app.models.user import User
from app.repositories.vacancy_repository import VacancyRepository
from app.repositories.application_repository import ApplicationRepository
from app.schemas.vacancy import VacancyCreate, VacancyOut, VacancyUpdate
from app.schemas.application import ApplicationForHROut
from app.services import llm_service
from app.services.file_parser import parse_file

router = APIRouter()


@router.post(
    "/parse-from-file",
    summary="Parse vacancy details from a file"
)
async def parse_vacancy_from_file(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_hr_user)
):
    try:
        text_content = await parse_file(file)
        if not text_content or not text_content.strip():
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь текст из файла. Возможно, файл является изображением или не содержит текстового слоя."
            )
        parsed_data = llm_service.parse_vacancy_from_text(text_content)
        if not parsed_data:
            raise HTTPException(status_code=400, detail="Could not parse vacancy details from the file.")
        return parsed_data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.get(
    "/{vacancy_id}/applications",
    response_model=List[ApplicationForHROut],
    summary="Get all applications for a specific vacancy"
)
def read_applications_for_vacancy(
        vacancy_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    vacancy_repo = VacancyRepository(db)
    vacancy = vacancy_repo.get_vacancy(vacancy_id)

    if not vacancy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    if vacancy.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access applications for this vacancy"
        )

    app_repo = ApplicationRepository(db)
    applications = app_repo.get_applications_for_vacancy(vacancy_id=vacancy_id)
    return applications


@router.post("/", response_model=VacancyOut, status_code=status.HTTP_201_CREATED)
def create_vacancy(
        vacancy_in: VacancyCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)

):
    vacancy_repo = VacancyRepository(db)
    return vacancy_repo.create_vacancy(
        vacancy_data=vacancy_in, owner_id=current_user.id
    )


@router.get("/", response_model=List[VacancyOut])
def read_vacancies(db: Session = Depends(get_db)):
    vacancy_repo = VacancyRepository(db)
    return vacancy_repo.get_all_vacancies()


@router.get("/my", response_model=List[VacancyOut])
def read_my_vacancies(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    vacancy_repo = VacancyRepository(db)
    return vacancy_repo.get_vacancies_by_owner(owner_id=current_user.id)


@router.get("/{vacancy_id}", response_model=VacancyOut)
def read_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy_repo = VacancyRepository(db)
    db_vacancy = vacancy_repo.get_vacancy(vacancy_id=vacancy_id)
    if db_vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return db_vacancy


@router.put("/{vacancy_id}", response_model=VacancyOut)
def update_vacancy(
        vacancy_id: int,
        vacancy_in: VacancyUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    vacancy_repo = VacancyRepository(db)
    updated_vacancy = vacancy_repo.update_vacancy(vacancy_id=vacancy_id, vacancy_data=vacancy_in)
    if updated_vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return updated_vacancy


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vacancy(
        vacancy_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    vacancy_repo = VacancyRepository(db)
    deleted_vacancy = vacancy_repo.delete_vacancy(vacancy_id=vacancy_id)
    if deleted_vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return  # Возвращаем пустой ответ со статусом 204
