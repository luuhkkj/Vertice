"""
Roteador de endpoints para o módulo de Participação, Atividades e Entregas (Bloco C — Fase 4).
"""

from datetime import date
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico
from app.database.connection import get_db
from app.modules.participacao.schemas import (
    AtividadeCreate,
    AtividadeResponse,
    AtividadeUpdate,
    EntregaAtividadeResponse,
    EntregaAtividadeUpdate,
    EntregaAtividadeUpsert,
    GeracaoEntregasEsperadasResponse,
)
from app.modules.participacao.service import ParticipacaoService
from app.modules.usuarios.models import Usuario

router = APIRouter()
entregas_router = APIRouter()


@router.post(
    "",
    response_model=AtividadeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar atividade",
)
def criar_atividade(
    dados: AtividadeCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AtividadeResponse:
    return ParticipacaoService.criar_atividade(
        db=db,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.get(
    "",
    response_model=list[AtividadeResponse],
    summary="Listar atividades no escopo do usuário autenticado",
)
def listar_atividades(
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[AtividadeResponse]:
    return ParticipacaoService.listar_atividades(
        db=db,
        usuario_autenticado=current_user,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        periodo_letivo=periodo_letivo,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{atividade_id}",
    response_model=AtividadeResponse,
    summary="Consultar uma atividade",
)
def obter_atividade(
    atividade_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AtividadeResponse:
    return ParticipacaoService.obter_atividade(
        db=db,
        atividade_id=atividade_id,
        usuario_autenticado=current_user,
    )


@router.patch(
    "/{atividade_id}",
    response_model=AtividadeResponse,
    summary="Atualizar uma atividade",
)
def atualizar_atividade(
    atividade_id: uuid.UUID,
    dados: AtividadeUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AtividadeResponse:
    return ParticipacaoService.atualizar_atividade(
        db=db,
        atividade_id=atividade_id,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.post(
    "/{atividade_id}/gerar-entregas-esperadas",
    response_model=GeracaoEntregasEsperadasResponse,
    status_code=status.HTTP_200_OK,
    summary="Gerar registros idempotentes de entregas esperadas para a turma",
)
def gerar_entregas_esperadas(
    atividade_id: uuid.UUID,
    data_referencia: Optional[date] = Query(
        default=None,
        description="Data opcional de referência para cálculo de PENDENTE vs NAO_ENTREGUE.",
    ),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> GeracaoEntregasEsperadasResponse:
    return ParticipacaoService.gerar_entregas_esperadas(
        db=db,
        atividade_id=atividade_id,
        usuario_autenticado=current_user,
        data_referencia=data_referencia,
    )


@router.get(
    "/{atividade_id}/entregas",
    response_model=list[EntregaAtividadeResponse],
    summary="Listar entregas esperadas e realizadas de uma atividade",
)
def listar_entregas_atividade(
    atividade_id: uuid.UUID,
    estudante_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[EntregaAtividadeResponse]:
    return ParticipacaoService.listar_entregas_atividade(
        db=db,
        atividade_id=atividade_id,
        usuario_autenticado=current_user,
        estudante_id=estudante_id,
    )


@router.post(
    "/{atividade_id}/entregas",
    response_model=EntregaAtividadeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar ou atualizar entrega de estudante em uma atividade",
)
def registrar_entrega_atividade(
    atividade_id: uuid.UUID,
    dados: EntregaAtividadeUpsert,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> EntregaAtividadeResponse:
    return ParticipacaoService.registrar_ou_atualizar_entrega(
        db=db,
        atividade_id=atividade_id,
        dados=dados,
        usuario_autenticado=current_user,
    )


@entregas_router.patch(
    "/{entrega_id}",
    response_model=EntregaAtividadeResponse,
    summary="Atualizar registro de entrega de atividade pelo ID",
)
def atualizar_entrega_por_id(
    entrega_id: uuid.UUID,
    dados: EntregaAtividadeUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> EntregaAtividadeResponse:
    return ParticipacaoService.atualizar_entrega_por_id(
        db=db,
        entrega_id=entrega_id,
        dados=dados,
        usuario_autenticado=current_user,
    )

