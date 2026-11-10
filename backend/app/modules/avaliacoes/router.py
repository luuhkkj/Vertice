"""
Roteador de endpoints para o módulo de Avaliações, Questões e Respostas (Bloco B — Fase 4).
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico
from app.database.connection import get_db
from app.modules.avaliacoes.schemas import (
    AvaliacaoCreate,
    AvaliacaoDetalhadaResponse,
    AvaliacaoResponse,
    AvaliacaoUpdate,
    QuestaoAvaliacaoCreate,
    QuestaoAvaliacaoResponse,
    QuestaoAvaliacaoUpdate,
    RespostaAvaliacaoCreate,
    RespostaAvaliacaoResponse,
)
from app.modules.avaliacoes.service import AvaliacaoService
from app.modules.usuarios.models import Usuario

router = APIRouter()
questoes_router = APIRouter()


@router.post(
    "",
    response_model=AvaliacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar avaliação",
)
def criar_avaliacao(
    dados: AvaliacaoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AvaliacaoResponse:
    return AvaliacaoService.criar_avaliacao(
        db=db,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.get(
    "",
    response_model=list[AvaliacaoResponse],
    summary="Listar avaliações no escopo do usuário autenticado",
)
def listar_avaliacoes(
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[AvaliacaoResponse]:
    return AvaliacaoService.listar_avaliacoes(
        db=db,
        usuario_autenticado=current_user,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        periodo_letivo=periodo_letivo,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{avaliacao_id}",
    response_model=AvaliacaoDetalhadaResponse,
    summary="Consultar detalhes e questões de uma avaliação",
)
def obter_avaliacao(
    avaliacao_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AvaliacaoDetalhadaResponse:
    return AvaliacaoService.obter_avaliacao(
        db=db,
        avaliacao_id=avaliacao_id,
        usuario_autenticado=current_user,
    )


@router.patch(
    "/{avaliacao_id}",
    response_model=AvaliacaoResponse,
    summary="Atualizar dados de uma avaliação",
)
def atualizar_avaliacao(
    avaliacao_id: uuid.UUID,
    dados: AvaliacaoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AvaliacaoResponse:
    return AvaliacaoService.atualizar_avaliacao(
        db=db,
        avaliacao_id=avaliacao_id,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.post(
    "/{avaliacao_id}/questoes",
    response_model=QuestaoAvaliacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar questão a uma avaliação",
)
def criar_questao(
    avaliacao_id: uuid.UUID,
    dados: QuestaoAvaliacaoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> QuestaoAvaliacaoResponse:
    return AvaliacaoService.criar_questao(
        db=db,
        avaliacao_id=avaliacao_id,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.get(
    "/{avaliacao_id}/questoes",
    response_model=list[QuestaoAvaliacaoResponse],
    summary="Listar questões de uma avaliação",
)
def listar_questoes(
    avaliacao_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[QuestaoAvaliacaoResponse]:
    return AvaliacaoService.listar_questoes(
        db=db,
        avaliacao_id=avaliacao_id,
        usuario_autenticado=current_user,
    )


@router.get(
    "/{avaliacao_id}/respostas",
    response_model=list[RespostaAvaliacaoResponse],
    summary="Listar respostas dos estudantes em uma avaliação",
)
def listar_respostas_avaliacao(
    avaliacao_id: uuid.UUID,
    questao_id: Optional[uuid.UUID] = Query(default=None),
    estudante_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[RespostaAvaliacaoResponse]:
    return AvaliacaoService.listar_respostas_avaliacao(
        db=db,
        avaliacao_id=avaliacao_id,
        usuario_autenticado=current_user,
        questao_id=questao_id,
        estudante_id=estudante_id,
    )


@questoes_router.patch(
    "/{questao_id}",
    response_model=QuestaoAvaliacaoResponse,
    summary="Atualizar questão de avaliação",
)
def atualizar_questao(
    questao_id: uuid.UUID,
    dados: QuestaoAvaliacaoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> QuestaoAvaliacaoResponse:
    return AvaliacaoService.atualizar_questao(
        db=db,
        questao_id=questao_id,
        dados=dados,
        usuario_autenticado=current_user,
    )


@questoes_router.post(
    "/{questao_id}/respostas",
    response_model=RespostaAvaliacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar resposta de estudante a uma questão",
)
def registrar_resposta_questao(
    questao_id: uuid.UUID,
    dados: RespostaAvaliacaoCreate,
    permitir_atualizacao: bool = Query(
        default=False,
        description="Se True, atualiza resposta já existente para o mesmo estudante e questão.",
    ),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> RespostaAvaliacaoResponse:
    return AvaliacaoService.registrar_resposta_questao(
        db=db,
        questao_id=questao_id,
        dados=dados,
        usuario_autenticado=current_user,
        permitir_atualizacao=permitir_atualizacao,
    )

