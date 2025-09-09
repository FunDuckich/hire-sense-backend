from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.services import security
from app.services.security import get_password_hash


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).filter(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(self, user: UserCreate) -> User:
        hashed_password = security.get_password_hash(user.password)
        db_user = User(**user.model_dump(exclude={"password"}), hashed_password=hashed_password)
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
