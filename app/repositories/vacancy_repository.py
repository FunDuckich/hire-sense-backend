from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.vacancy import Vacancy, EvaluationCriterion
from app.schemas.vacancy import VacancyCreate


class VacancyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_vacancy(self, vacancy_data: VacancyCreate) -> Vacancy:
        vacancy_dict = vacancy_data.model_dump(exclude={'evaluation_criteria'})
        db_vacancy = Vacancy(**vacancy_dict)

        for criterion_data in vacancy_data.evaluation_criteria:
            db_criterion = EvaluationCriterion(
                criterion=criterion_data.criterion,
                weight=criterion_data.weight
            )
            db_vacancy.evaluation_criteria.append(db_criterion)

        self.db.add(db_vacancy)
        self.db.commit()
        self.db.refresh(db_vacancy)
        return db_vacancy

    def get_vacancy(self, vacancy_id: int) -> Vacancy | None:
        statement = select(Vacancy).options(joinedload(Vacancy.evaluation_criteria)).where(Vacancy.id == vacancy_id)
        return self.db.execute(statement).unique().scalar_one_or_none()

    def get_all_vacancies(self) -> list[Vacancy]:
        statement = select(Vacancy).options(joinedload(Vacancy.evaluation_criteria))
        return self.db.execute(statement).unique().scalars().all()
