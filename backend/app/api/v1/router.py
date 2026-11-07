"""
Roteador central da API v1.
Concentra e organiza os endpoints da versão 1 da aplicação Vértice.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.modules.atribuicoes.router import router as atribuicoes_router
from app.modules.auth.router import router as auth_router
from app.modules.disciplinas.router import router as disciplinas_router
from app.modules.escolas.router import router as escolas_router
from app.modules.turmas.router import router as turmas_router
from app.modules.usuarios.router import router as usuarios_router

api_router = APIRouter()


@api_router.get("/health", tags=["Health"])
def api_v1_health() -> dict[str, str]:
    """
    Verificação de funcionamento e integridade específica da versão 1 da API.
    """
    return {
        "status": "healthy",
        "api_version": "v1",
        "project": settings.PROJECT_NAME,
        "release": settings.VERSION,
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
