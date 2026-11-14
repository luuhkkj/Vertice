"""
Módulo de configurações centrais da aplicação Vértice.
Utiliza Pydantic v2 e pydantic-settings para carregamento e validação rigorosa de variáveis de ambiente.
Não possui chaves JWT ou credenciais de banco de dados padrão fixas no código.
"""

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote_plus

from pydantic import BeforeValidator, computed_field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = BACKEND_DIR / ".env"

INSECURE_SECRET_PATTERNS = {
    "change-this-secret-key-in-production-vertice-edu-2026-min-32-chars",
    "change-this",
    "changeme",
    "secret",
    "default",
    "password",
    "12345678901234567890123456789012",
}

INSECURE_PROD_DB_PASSWORDS = {
    "postgres",
    "admin",
    "password",
    "123456",
    "root",
}


def parse_cors(v: Any) -> list[str]:
    """Converte lista de origens em formato JSON ou separado por vírgula em lista de strings."""
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        if v.startswith("[") and v.endswith("]"):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, (list, set, tuple)):
        return [str(i).strip() for i in v if str(i).strip()]
    return []


class Settings(BaseSettings):
    """
    Configurações globais carregadas a partir de variáveis de ambiente e/ou arquivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Aplicação
    PROJECT_NAME: str = "Vértice Backend API"
    VERSION: str = "0.2.1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[
        list[str],
        NoDecode,
        BeforeValidator(parse_cors),
    ] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    # Banco de Dados PostgreSQL (sem credenciais padrão fixas no código)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None
    DATABASE_URL: str | None = None

    # Segurança & JWT (SECRET_KEY obrigatória via ambiente, sem valor padrão)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @model_validator(mode="after")
    def validar_seguranca_configuracoes(self) -> "Settings":
        """
        Impede inicialização com segredo JWT fraco/padrão, sem credenciais de banco
        ou com configurações inseguras em ambiente de produção.
        """
        env_norm = self.ENVIRONMENT.strip().lower()
        if env_norm not in ("development", "dev", "test", "testing", "staging", "production", "prod"):
            raise ValueError(
                f"ENVIRONMENT inválido: '{self.ENVIRONMENT}'. Use development, test, staging ou production."
            )

        secret_clean = self.SECRET_KEY.strip() if self.SECRET_KEY else ""
        if len(secret_clean) < 32:
            raise ValueError(
                "SECRET_KEY deve possuir no mínimo 32 caracteres. Configure uma chave segura no ambiente/.env."
            )
        if (
            secret_clean.lower() in INSECURE_SECRET_PATTERNS
            or "change-this" in secret_clean.lower()
            or "change-me" in secret_clean.lower()
            or "changeme" in secret_clean.lower()
        ):
            raise ValueError(
                "SECRET_KEY utiliza um valor padrão/placeholder inseguro. Gere um segredo exclusivo para o ambiente."
            )

        has_db_url = bool(self.DATABASE_URL and self.DATABASE_URL.strip())
        has_pg_parts = bool(
            self.POSTGRES_SERVER
            and self.POSTGRES_USER
            and self.POSTGRES_PASSWORD
            and self.POSTGRES_DB
        )
        if not has_db_url and not has_pg_parts:
            raise ValueError(
                "Configuração de banco de dados incompleta: defina DATABASE_URL ou "
                "(POSTGRES_SERVER, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) no ambiente."
            )

        if env_norm in ("production", "prod"):
            if self.DEBUG:
                raise ValueError(
                    "Configuração insegura: DEBUG=True não é permitido em produção (ENVIRONMENT=production)."
                )
            if not self.BACKEND_CORS_ORIGINS or "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError(
                    "Configuração insegura: BACKEND_CORS_ORIGINS não pode estar vazio ou conter '*' em produção."
                )
            if has_db_url and self.DATABASE_URL and self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "Configuração insegura: SQLite não é permitido em produção. Utilize PostgreSQL."
                )
            if self.POSTGRES_PASSWORD and self.POSTGRES_PASSWORD.strip().lower() in INSECURE_PROD_DB_PASSWORDS:
                raise ValueError(
                    "Configuração insegura: POSTGRES_PASSWORD utiliza uma senha fraca/padrão em produção."
                )

        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Retorna a URI completa para conexão com o PostgreSQL via psycopg."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        user_enc = quote_plus(self.POSTGRES_USER or "")
        pwd_enc = quote_plus(self.POSTGRES_PASSWORD or "")
        return (
            f"postgresql+psycopg://{user_enc}:{pwd_enc}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
