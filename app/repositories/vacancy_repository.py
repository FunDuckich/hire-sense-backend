from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.vacancy import Vacancy, EvaluationCriterion
from app.schemas.vacancy import VacancyCreate, VacancyUpdate


class VacancyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_vacancy(self, vacancy_data: VacancyCreate, owner_id: int) -> Vacancy:
        vacancy_dict = vacancy_data.model_dump(exclude={'evaluation_criteria'})
        db_vacancy = Vacancy(**vacancy_dict, owner_id=owner_id)

        for criterion_data in vacancy_data.evaluation_criteria:
            db_criterion = EvaluationCriterion(**criterion_data.model_dump())
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

    def update_vacancy(self, vacancy_id: int, vacancy_data: "VacancyUpdate") -> Vacancy | None:
        db_vacancy = self.db.get(Vacancy, vacancy_id)
        if not db_vacancy:
            return None

        update_data = vacancy_data.model_dump(exclude_unset=True)

        new_criteria_data = update_data.pop("evaluation_criteria", None)

        for key, value in update_data.items():
            setattr(db_vacancy, key, value)

        if new_criteria_data is not None:
            for old_criterion in db_vacancy.evaluation_criteria:
                self.db.delete(old_criterion)

            for criterion_data in new_criteria_data:
                new_criterion = EvaluationCriterion(
                    criterion=criterion_data['criterion'],
                    weight=criterion_data['weight']
                )
                db_vacancy.evaluation_criteria.append(new_criterion)

        # 4. Сохраняем все изменения
        self.db.commit()
        self.db.refresh(db_vacancy)
        return db_vacancy

    def delete_vacancy(self, vacancy_id: int) -> Vacancy | None:
        db_vacancy = self.get_vacancy(vacancy_id=vacancy_id)
        if not db_vacancy:
            return None

        self.db.delete(db_vacancy)
        self.db.commit()
        return db_vacancy

    def get_vacancies_by_owner(self, owner_id: int) -> list[Vacancy]:
        statement = select(Vacancy).options(
            joinedload(Vacancy.evaluation_criteria)
        ).where(Vacancy.owner_id == owner_id)

        return self.db.execute(statement).unique().scalars().all()
