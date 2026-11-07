"""
Configurações e fixtures globais do pytest para testes da API Vértice.
"""

import os
import sys
from typing import Generator
import pytest
from fastapi.testclient import TestClient

# Garante que o diretório raiz do backend esteja no sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """
    Fixture que fornece um cliente HTTP para efetuar requisições nos testes,
    sem necessitar de inicialização de servidor real nem conexão com banco de dados.
    """
    with TestClient(app) as test_client:
        yield test_client

