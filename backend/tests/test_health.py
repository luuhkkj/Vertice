"""
Testes operacionais de integridade (health checks), documentação e segurança básica.
"""

from fastapi.testclient import TestClient

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
    """Verifica se GET /health retorna HTTP 200 e status operacional saudável."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
    assert "timestamp" in data


def test_api_v1_health_check_returns_version(client: TestClient) -> None:
    """Verifica se GET /api/v1/health retorna HTTP 200 com a versão da API."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"


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

