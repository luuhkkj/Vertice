"""
Roteador de consulta de Estudantes e Histórico Escolar (somente leitura na Fase 3).
Não possui endpoints de criação ou edição manual individual; os dados são alimentados
exclusivamente pelo fluxo de importação validada em duas etapas.
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_importacao_datasets
from app.database.connection import get_db
from app.modules.estudantes.schemas import (
    EstudanteHistoricoDetalhadoResponse,
    EstudanteResponse,
)
from app.modules.estudantes.service import EstudanteService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.get(
    "",
    response_model=list[EstudanteResponse],
    summary="Listar estudantes no escopo autorizado",
    description=(
        "Retorna estudantes anonimizados filtrados pelo escopo do usuário autenticado "
        "(escola do gestor ou turmas/disciplinas vinculadas ao professor). "
        "Inclui o cabeçalho HTTP `X-Total-Count` com o total de estudantes distintos no escopo."
    ),
)
def listar_estudantes(
    response: Response,
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None),
    periodo_letivo: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> list[EstudanteResponse]:
    estudantes = EstudanteService.listar_estudantes(
        db=db,
        usuario_solicitante=current_user,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
        skip=skip,
        limit=limit,
    )
    total = EstudanteService.contar_estudantes(
        db=db,
        usuario_solicitante=current_user,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
    )
    response.headers["X-Total-Count"] = str(total)
    return [EstudanteResponse.model_validate(e) for e in estudantes]


@router.get(
    "/{estudante_id}",
    response_model=EstudanteHistoricoDetalhadoResponse,
    summary="Obter estudante e seu histórico longitudinal",
    description=(
        "Retorna os dados anonimizados e o histórico de boletins e notas por disciplina "
        "do estudante, filtrado rigorosamente pelo escopo autorizado do solicitante."
    ),
)
def obter_estudante(
    estudante_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> EstudanteHistoricoDetalhadoResponse:
    return EstudanteService.obter_estudante_com_historico(
        db=db,
        estudante_id=estudante_id,
        usuario_solicitante=current_user,
    )

