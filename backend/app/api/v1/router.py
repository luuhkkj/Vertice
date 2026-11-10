"""
Roteador central da API v1.
Concentra e organiza os endpoints da versão 1 da aplicação Vértice.
"""

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import check_database_connection, get_db
from app.modules.atribuicoes.router import router as atribuicoes_router
from app.modules.auth.router import router as auth_router
from app.modules.disciplinas.router import router as disciplinas_router
from app.modules.escolas.router import router as escolas_router
from app.modules.turmas.router import router as turmas_router
from app.modules.usuarios.router import router as usuarios_router

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
def api_v1_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Verificação de funcionamento e integridade da versão 1 da API,
    distinguindo claramente a disponibilidade da API e do banco de dados.
    """
    db_up = check_database_connection(db)
    return {
        "status": "healthy" if db_up else "degraded",
        "api_version": "v1",
        "project": settings.PROJECT_NAME,
        "release": settings.VERSION,
        "components": {
            "api": "up",
            "database": "up" if db_up else "down",
        },
    }


# ==============================================================================
# Inclusão dos roteadores dos módulos de negócio (Fase 2)
# ==============================================================================
api_router.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(usuarios_router, prefix="/usuarios", tags=["Usuários"])
api_router.include_router(escolas_router, prefix="/escolas", tags=["Escolas"])
api_router.include_router(turmas_router, prefix="/turmas", tags=["Turmas"])
api_router.include_router(
    disciplinas_router, prefix="/disciplinas", tags=["Disciplinas"]
)
api_router.include_router(
    atribuicoes_router, prefix="/atribuicoes", tags=["Atribuições"]
)
