from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.user import UserCreate, UserOut, Role
from app.schemas.token import Token
from app.repositories.user_repository import UserRepository
from app.services import security
from app.core.config import settings
from app.api.dependencies import get_db

router = APIRouter()


@router.post("/candidate/register", response_model=UserOut)
def register_candidate(user_in: UserCreate, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    db_user = user_repo.get_user_by_email(email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user_in.role = Role.CANDIDATE
    return user_repo.create_user(user=user_in)


@router.post("/hr/register", response_model=UserOut)
def register_hr(user_in: UserCreate, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    db_user = user_repo.get_user_by_email(email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if not user_in.company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name is required for HR",
        )
    user_in.role = Role.HR
    return user_repo.create_user(user=user_in)


@router.post("/login", response_model=Token)
def login_for_access_token(
        db: Session = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends()
):
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
