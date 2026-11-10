"""
Testes operacionais de integridade (health checks), documentação,
validação de segurança de configurações e utilitários criptográficos.
"""

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_app_starts_and_root_responds(client: TestClient) -> None:
    """Verifica se a aplicação inicia e responde na rota raiz com dados do projeto."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["health_check"] == "/health"
    assert data["docs_url"] == "/docs"


def test_health_check_returns_ok_status(client: TestClient) -> None:
    """Verifica se GET /health retorna HTTP 200 e distingue disponibilidade da API e do banco."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"] == {"api": "up", "database": "up"}
    assert "environment" in data
    assert "timestamp" in data


def test_health_check_detects_database_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica se os endpoints de health check reportam status 'degraded' quando o banco falha, mantendo API 'up'."""
    from sqlalchemy.exc import OperationalError

    def _broken_execute(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OperationalError("SELECT 1", {}, Exception("Connection refused"))

    monkeypatch.setattr(Session, "execute", _broken_execute)

    resp_root = client.get("/health")
    assert resp_root.status_code == 200
    data_root = resp_root.json()
    assert data_root["status"] == "degraded"
    assert data_root["components"]["api"] == "up"
    assert data_root["components"]["database"] == "down"

    resp_v1 = client.get("/api/v1/health")
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] == "degraded"
    assert data_v1["components"]["api"] == "up"
    assert data_v1["components"]["database"] == "down"


def test_api_v1_health_check_returns_version(client: TestClient) -> None:
    """Verifica se GET /api/v1/health retorna HTTP 200 com a versão da API e status dos componentes."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"
    assert data["components"] == {"api": "up", "database": "up"}


def test_swagger_documentation_available(client: TestClient) -> None:
    """Verifica se a interface Swagger UI em /docs está acessível (HTTP 200)."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_openapi_schema_available(client: TestClient) -> None:
    """Verifica se o esquema OpenAPI JSON está acessível."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "/health" in data["paths"]


def test_security_password_hashing() -> None:
    """Verifica geração e validação de hash seguro de senhas."""
    password = "SenhaSuperSecreta@123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("SenhaIncorreta", hashed) is False


def test_security_jwt_token_creation_and_decoding() -> None:
    """Verifica criação e validação de tokens JWT."""
    subject = "user-uuid-12345"
    token = create_access_token(subject=subject)

    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload["sub"] == subject
    assert "exp" in payload
    assert "iat" in payload


def test_settings_rejects_short_or_default_secret_key() -> None:
    """Garante que a configuração rejeita SECRET_KEY curta ou padrão de exemplo."""
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            SECRET_KEY="chave-curta",
            DATABASE_URL="sqlite:///:memory:",
        )

    with pytest.raises(ValidationError, match="inseguro"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            SECRET_KEY="change-me-in-production-use-a-long-random-secret-key",
            DATABASE_URL="sqlite:///:memory:",
        )


def test_settings_rejects_insecure_production_config() -> None:
    """Garante que a aplicação não inicializa em produção com configuração insegura."""
    valid_secret = "a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8"

    # 1. DEBUG=True em produção deve falhar
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENVIRONMENT="production",
            DEBUG=True,
            SECRET_KEY=valid_secret,
            DATABASE_URL=None,
            POSTGRES_USER="vertice_prod",
            POSTGRES_PASSWORD="StrongProdPassword#2026",
            POSTGRES_DB="vertice_prod",
        )

    # 2. Senha fraca de banco em produção deve falhar
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY=valid_secret,
            DATABASE_URL=None,
            POSTGRES_USER="vertice_prod",
            POSTGRES_PASSWORD="postgres",
            POSTGRES_DB="vertice_prod",
        )

    # 3. CORS wildcard '*' em produção deve falhar
    with pytest.raises(ValidationError, match="BACKEND_CORS_ORIGINS"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY=valid_secret,
            BACKEND_CORS_ORIGINS=["*"],
            DATABASE_URL=None,
            POSTGRES_USER="vertice_prod",
            POSTGRES_PASSWORD="StrongProdPassword#2026",
            POSTGRES_DB="vertice_prod",
        )

    # 4. SQLite em produção deve falhar
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            ENVIRONMENT="production",
            DEBUG=False,
            SECRET_KEY=valid_secret,
            DATABASE_URL="sqlite:///:memory:",
        )


