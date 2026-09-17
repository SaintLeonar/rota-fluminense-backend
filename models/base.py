import os
from collections.abc import Mapping

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL_ENV_VAR = "DATABASE_URL"


class DatabaseConfigurationError(RuntimeError):
    """Indica uma configuração de banco ausente ou inválida."""


def load_database_url(environment: Mapping[str, str] | None = None) -> URL:
    """Obtém e valida a URL SQLAlchemy configurada no ambiente."""
    source = os.environ if environment is None else environment
    raw_url = source.get(DATABASE_URL_ENV_VAR)

    if raw_url is None or not raw_url.strip():
        raise DatabaseConfigurationError(
            "A variável de ambiente DATABASE_URL é obrigatória. "
            "Defina uma URL SQLAlchemy completa antes de iniciar a aplicação."
        )

    try:
        database_url = make_url(raw_url.strip())
    except ArgumentError:
        raise DatabaseConfigurationError(
            "A variável de ambiente DATABASE_URL deve conter uma URL "
            "SQLAlchemy válida com dialeto e banco de dados."
        ) from None

    if not database_url.drivername or not database_url.database:
        raise DatabaseConfigurationError(
            "A variável de ambiente DATABASE_URL deve conter uma URL "
            "SQLAlchemy válida com dialeto e banco de dados."
        )

    return database_url


def build_engine(database_url: URL) -> Engine:
    """Cria o engine sem opções específicas de SQLite."""
    try:
        return create_engine(database_url, pool_pre_ping=True)
    except (ArgumentError, ImportError):
        raise DatabaseConfigurationError(
            "Não foi possível inicializar o banco configurado "
            "em DATABASE_URL. "
            "Verifique o dialeto, o driver instalado e o formato da URL."
        ) from None


DATABASE_URL = load_database_url()
engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
