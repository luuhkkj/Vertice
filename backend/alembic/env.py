import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Adiciona o diretório raiz do backend ao sys.path para importação do módulo app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
import app.database  # noqa: F401 - garante que todos os modelos ORM sejam carregados no Base.metadata
from app.database.base import Base

# Objeto de configuração do Alembic
config = context.config

# Interpreta o arquivo de configuração para o logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadados do SQLAlchemy para geração automática de migrações
target_metadata = Base.metadata


def get_database_url() -> str:
    """Obtém a URL de banco priorizando a configuração do ambiente ou do alembic.ini."""
    env_url = os.getenv("ALEMBIC_DATABASE_URL")
    if env_url:
        return env_url
    return settings.SQLALCHEMY_DATABASE_URI


def run_migrations_offline() -> None:
    """Executa migrações no modo 'offline', gerando scripts SQL sem conexão ativa."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações no modo 'online', aplicando diretamente no banco."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
