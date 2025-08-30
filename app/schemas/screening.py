from pydantic import BaseModel


class ScreeningResultSummaryOut(BaseModel):
    overall_match_score: int

    class Config:
        from_attributes = True
