"""
Configurações e fixtures globais do pytest para testes isolados da API Vértice.
Utiliza banco SQLite em memória isolado por teste, sem exigir instância PostgreSQL ativa.
"""

import os
import sys
from typing import Generator

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Garante que o diretório raiz do backend esteja no sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Configura variáveis de ambiente próprias e seguras para a suíte de testes
# antes de importar app.core.config, não dependendo de arquivo .env local
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "True"
os.environ["SECRET_KEY"] = "chave-secreta-isolada-para-suite-de-testes-automatizados-vertice-2026"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import app.database  # noqa: F401 - garante carregamento de todos os modelos ORM
from app.database.base import Base
from app.database.connection import get_db
from app.main import app

# Motor de banco isolado em memória para a suíte de testes unitários e de integração
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Cria todas as tabelas em um banco em memória limpo antes de cada teste
    e remove tudo ao final para isolamento total.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP TestClient com a dependência get_db sobrescrita para usar a sessão de teste.
    """

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
