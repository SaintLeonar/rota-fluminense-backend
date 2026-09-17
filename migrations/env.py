from logging.config import fileConfig

from alembic import context

from models.avaliacao import Avaliacao
from models.base import DATABASE_URL, Base, engine
from models.local_turistico import LocalTuristico

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

MODELS = (Avaliacao, LocalTuristico)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa migrações sem abrir conexão com o banco."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações usando o engine configurado pela aplicação."""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
