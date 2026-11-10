"""
Roteador de endpoints para o módulo de Acompanhamento Pedagógico (Fase 4).
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico
from app.database.connection import get_db
from app.modules.acompanhamento.models import OrigemAcompanhamento
from app.modules.acompanhamento.schemas import (
    AcompanhamentoCreate,
    AcompanhamentoResponse,
    AcompanhamentoUpdate,
)
from app.modules.acompanhamento.service import AcompanhamentoService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "",
    response_model=AcompanhamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar ação ou acompanhamento pedagógico",
)
def criar_acompanhamento(
    dados: AcompanhamentoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AcompanhamentoResponse:
    return AcompanhamentoService.criar_acompanhamento(
        db=db,
        dados=dados,
        usuario_autenticado=current_user,
    )


@router.get(
    "",
    response_model=list[AcompanhamentoResponse],
    summary="Listar acompanhamentos pedagógicos no escopo do usuário",
)
def listar_acompanhamentos(
    turma_id: Optional[uuid.UUID] = Query(default=None),
    estudante_id: Optional[uuid.UUID] = Query(default=None),
    origem: Optional[OrigemAcompanhamento] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[AcompanhamentoResponse]:
    return AcompanhamentoService.listar_acompanhamentos(
        db=db,
        usuario_autenticado=current_user,
        turma_id=turma_id,
        estudante_id=estudante_id,
        origem=origem,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{acompanhamento_id}",
    response_model=AcompanhamentoResponse,
    summary="Consultar detalhes e histórico de um acompanhamento pedagógico",
)
def obter_acompanhamento(
    acompanhamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AcompanhamentoResponse:
    return AcompanhamentoService.obter_acompanhamento(
        db=db,
        acompanhamento_id=acompanhamento_id,
        usuario_autenticado=current_user,
    )


@router.patch(
    "/{acompanhamento_id}",
    response_model=AcompanhamentoResponse,
    summary="Atualizar acompanhamento pedagógico preservando histórico de edições",
)
def atualizar_acompanhamento(
    acompanhamento_id: uuid.UUID,
    dados: AcompanhamentoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> AcompanhamentoResponse:
    return AcompanhamentoService.atualizar_acompanhamento(
        db=db,
        acompanhamento_id=acompanhamento_id,
        dados=dados,
        usuario_autenticado=current_user,
    )

