from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.v1 import auth as auth_v1
from app.api.v1 import vacancies as vacancies_v1
from app.api.v1 import applications as applications_v1


@asynccontextmanager
async def lifespan(app_local: FastAPI):
    # Код здесь выполняется при старте приложения
    print("Приложение запускается...")
    yield
    # Код здесь выполняется при остановке приложения
    print("Приложение останавливается...")


app = FastAPI(title="Hire Sense API", lifespan=lifespan)

app.include_router(auth_v1.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(vacancies_v1.router, prefix="/api/v1/vacancies", tags=["Vacancies"])
app.include_router(applications_v1.router, prefix="/api/v1", tags=["Applications"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Hire Sense API"}
