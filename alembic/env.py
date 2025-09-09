from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.database import Base
from app.models.user import User
from app.models.vacancy import Vacancy, EvaluationCriterion
from app.models.application import Application
from app.models.interview import InterviewSession, InterviewTranscript
from app.models.screening import ApplicationScreeningResult
from app.models.report import InterviewReport

import sys

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.core.database import Base
from app.models.user import User
from app.models.vacancy import Vacancy, EvaluationCriterion
from app.models.application import Application
from app.models.screening import ApplicationScreeningResult
from app.models.interview import InterviewSession, InterviewTranscript
from app.models.report import InterviewReport

target_metadata = Base.metadata


from dotenv import load_dotenv
import os

project_root = os.path.dirname(config.config_file_name)
dotenv_path = os.path.join(project_root, '.env')

if os.path.exists(dotenv_path):
    print(f"Загрузка переменных окружения из: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"ВНИМАНИЕ: файл .env не найден по пути {dotenv_path}")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from app.core.config import settings  # Импортируем наши настройки
    from sqlalchemy import engine_from_config, pool

    config_section = config.get_section(config.config_ini_section)

    sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    config_section['sqlalchemy.url'] = sync_db_url

    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
