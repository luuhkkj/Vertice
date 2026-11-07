"""
Roteador central da API v1.
Concentra e organiza os endpoints da versão 1 da aplicação Vértice.
"""

from fastapi import APIRouter

from app.core.config import settings

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
# Inclusão futura de roteadores dos módulos de negócio:
# Exemplo:
# from app.modules.auth.router import router as auth_router
# from app.modules.usuarios.router import router as usuarios_router
# from app.modules.estudantes.router import router as estudantes_router
#
# api_router.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
# api_router.include_router(usuarios_router, prefix="/usuarios", tags=["Usuários"])
# api_router.include_router(estudantes_router, prefix="/estudantes", tags=["Estudantes"])
# ==============================================================================

