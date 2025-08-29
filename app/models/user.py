import enum
from sqlalchemy import Column, Integer, String, Enum
from app.core.database import Base
from sqlalchemy.orm import relationship


class Role(str, enum.Enum):
    CANDIDATE = "CANDIDATE"
    HR = "HR"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    company_name = Column(String, nullable=True)  # Только для HR
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    applications = relationship("Application", back_populates="candidate")
