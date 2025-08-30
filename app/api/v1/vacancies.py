from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_hr_user
from app.models.user import User
from app.repositories.vacancy_repository import VacancyRepository
from app.schemas.vacancy import VacancyCreate, VacancyOut, VacancyUpdate

router = APIRouter()


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
