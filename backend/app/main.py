"""
Ponto de entrada principal da aplicação FastAPI - Backend Vértice.
"""

from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.database.connection import check_database_connection, get_db

logger = logging.getLogger("vertice.api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "API do sistema Vértice para gestão e análise de dados educacionais, "
        "indicadores de aprendizagem, modelos preditivos e assistente inteligente."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configuração de CORS controlada rigorosamente por variável de ambiente
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ==============================================================================
# Tratamento centralizado de exceções
# ==============================================================================
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Tratamento padronizado para erros HTTP conhecidos."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Tratamento padronizado para falhas de validação de esquemas Pydantic."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
async def database_operational_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Tratamento específico para falhas de conectividade com o banco de dados PostgreSQL."""
    logger.error("Erro operacional de conexão com o banco de dados: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "Serviço de banco de dados temporariamente indisponível. Verifique a conexão com o PostgreSQL."
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Tratamento para erros gerais de persistência do SQLAlchemy."""
    logger.error("Erro de banco de dados: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro ao processar operação no banco de dados."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Tratamento para exceções inesperadas para não expor rastros de erro em produção."""
    logger.exception("Erro não tratado durante a requisição: %s", exc)
    detail_msg = (
        str(exc) if settings.DEBUG else "Ocorreu um erro interno no servidor."
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail_msg},
    )


# ==============================================================================
# Endpoints raiz e de verificação operacional
# ==============================================================================
@app.get("/", tags=["Root"])
def read_root() -> dict[str, Any]:
    """Retorna informações gerais da API e atalhos para documentação e health checks."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "health_check": "/health",
        "api_v1_health": f"{settings.API_V1_STR}/health",
    }


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Verificação operacional do serviço que distingue explicitamente
    a disponibilidade da API e a disponibilidade do banco de dados.
    """
    db_up = check_database_connection(db)
    return {
        "status": "healthy" if db_up else "degraded",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api": "up",
            "database": "up" if db_up else "down",
        },
    }


# ==============================================================================
# Inclusão do roteador versionado v1
# ==============================================================================
app.include_router(api_router, prefix=settings.API_V1_STR)
