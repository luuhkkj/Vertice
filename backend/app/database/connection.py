"""
Gerenciamento de conexão com o banco de dados e ciclo de vida de sessões SQLAlchemy 2.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("vertice.database")

# Criação do motor do SQLAlchemy 2
# pool_pre_ping garante reconexão transparente caso o banco feche conexões ociosas
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    echo=False,
)

# Fábrica de sessões configurada para transações explícitas
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependência FastAPI para injeção de sessões de banco de dados.
    Efetua rollback em caso de exceção de banco e garante o fechamento seguro da sessão.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Erro durante operação no banco de dados: %s", exc)
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Testa se a conexão com o banco de dados configurado está ativa.
    Retorna True se operacional ou False em caso de falha de conexão.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Falha ao verificar conexão com o banco de dados: %s", exc)
        return False
