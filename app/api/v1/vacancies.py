from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.vacancy import VacancyCreate, VacancyOut
from app.repositories.vacancy_repository import VacancyRepository
from app.api.dependencies import get_db, get_current_hr_user

router = APIRouter()


@router.post("/", response_model=VacancyOut, status_code=status.HTTP_201_CREATED)
def create_vacancy(
        vacancy_in: VacancyCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)

):
    vacancy_repo = VacancyRepository(db)
    return vacancy_repo.create_vacancy(vacancy_data=vacancy_in)


@router.get("/", response_model=List[VacancyOut])
def read_vacancies(db: Session = Depends(get_db)):
    vacancy_repo = VacancyRepository(db)
    return vacancy_repo.get_all_vacancies()


@router.get("/{vacancy_id}", response_model=VacancyOut)
def read_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy_repo = VacancyRepository(db)
    db_vacancy = vacancy_repo.get_vacancy(vacancy_id=vacancy_id)
    if db_vacancy is None:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return db_vacancy
