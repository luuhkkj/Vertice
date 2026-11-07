"""
Gerenciamento de conexão com o banco de dados e ciclo de vida de sessões SQLAlchemy 2.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Criação do motor do SQLAlchemy 2
# pool_pre_ping garante reconexão transparente caso o banco feche conexões ociosas
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Fábrica de sessões configurada para transações manuais explícitas
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependência FastAPI para injeção de sessões de banco de dados.
    Garante o fechamento seguro da sessão após o término da requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

