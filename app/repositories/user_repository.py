from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.security import get_password_hash


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user: UserCreate) -> User:
        hashed_password = get_password_hash(user.password)
        db_user = User(
            email=user.email,
            name=user.name,
            hashed_password=hashed_password,
            company_name=user.company_name,
            role=user.role
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
