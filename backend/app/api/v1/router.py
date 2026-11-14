"""
Roteador central da API v1.
Concentra e organiza os endpoints da versão 1 da aplicação Vértice.
"""

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import check_database_connection, get_db
from app.integrations.assistant.router import router as assistant_router
from app.integrations.prediction.router import router as prediction_router
from app.modules.acompanhamento.router import router as acompanhamento_router
from app.modules.atribuicoes.router import router as atribuicoes_router
from app.modules.auth.router import router as auth_router
from app.modules.avaliacoes.router import (
    questoes_router,
    router as avaliacoes_router,
)
from app.modules.disciplinas.router import router as disciplinas_router
from app.modules.escolas.router import router as escolas_router
from app.modules.estudantes.router import router as estudantes_router
from app.modules.importacao.router import router as importacao_router
from app.modules.indicadores.router import router as indicadores_router
from app.modules.participacao.router import (
    entregas_router,
    router as participacao_router,
)
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
# Inclusão dos roteadores dos módulos de negócio (Fases 2, 3 e 4)
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
api_router.include_router(
    estudantes_router, prefix="/estudantes", tags=["Estudantes"]
)
api_router.include_router(
    importacao_router, prefix="/importacoes", tags=["Importações"]
)
api_router.include_router(
    avaliacoes_router, prefix="/avaliacoes", tags=["Avaliações"]
)
api_router.include_router(
    questoes_router, prefix="/questoes", tags=["Avaliações"]
)
api_router.include_router(
    participacao_router, prefix="/atividades", tags=["Participação e Atividades"]
)
api_router.include_router(
    entregas_router, prefix="/entregas", tags=["Participação e Atividades"]
)
api_router.include_router(
    acompanhamento_router,
    prefix="/acompanhamentos",
    tags=["Acompanhamento Pedagógico"],
)
api_router.include_router(
    indicadores_router, prefix="/indicadores", tags=["Indicadores"]
)
api_router.include_router(
    prediction_router, prefix="/previsoes", tags=["Previsões Preditivas"]
)
api_router.include_router(
    assistant_router, prefix="/assistente", tags=["Assistente IA"]
)
