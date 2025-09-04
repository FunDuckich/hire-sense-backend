from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.database import SessionLocal
from app.core.config import settings
from app.schemas.token import TokenData
from app.models.user import User, Role
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user


def get_current_hr_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != Role.HR:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


def get_current_hr_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != Role.HR:
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


def get_current_candidate_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != Role.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user
