from pydantic import BaseModel, EmailStr
from app.models.user import Role


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    company_name: str | None = None
    role: Role


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: Role
    company_name: str | None = None

    class Config:
        from_attributes = True
