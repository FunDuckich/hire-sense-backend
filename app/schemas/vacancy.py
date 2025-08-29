from pydantic import BaseModel, constr, conint


class EvaluationCriterionBase(BaseModel):
    criterion: constr(min_length=1)
    weight: conint(gt=0, le=100)


class EvaluationCriterionCreate(EvaluationCriterionBase):
    pass


class EvaluationCriterionOut(EvaluationCriterionBase):
    id: int

    class Config:
        from_attributes = True


class VacancyBase(BaseModel):
    job_title: str
    company_name: str | None = None
    location: str | None = None
    salary_range: str | None = None
    key_responsibilities: str | None = None
    tech_stack: str | None = None
    required_experience: str | None = None
    hard_skills: str | None = None
    soft_skills: str | None = None
    education: str | None = None
    what_we_offer: str | None = None


class VacancyCreate(VacancyBase):
    evaluation_criteria: list[EvaluationCriterionCreate]


class VacancyOut(VacancyBase):
    id: int
    evaluation_criteria: list[EvaluationCriterionOut]

    class Config:
        from_attributes = True


class VacancyUpdate(BaseModel):
    job_title: str | None = None
    company_name: str | None = None
    location: str | None = None
    salary_range: str | None = None
    key_responsibilities: str | None = None
    tech_stack: str | None = None
    required_experience: str | None = None
    hard_skills: str | None = None
    soft_skills: str | None = None
    education: str | None = None
    what_we_offer: str | None = None
    # обновление критериев - более сложная логика, пока оставим
    # evaluation_criteria: list[EvaluationCriterionCreate] | None = None
