"""
Roteador de endpoints para o módulo de Indicadores Educacionais (Fase 4):
- GET /api/v1/indicadores/gerais
- GET /api/v1/indicadores/avaliacoes
- GET /api/v1/indicadores/participacao
"""

from datetime import date
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico
from app.database.connection import get_db
from app.modules.indicadores.schemas import (
    IndicadoresAvaliacoesResponse,
    IndicadoresGeraisResponse,
    IndicadoresParticipacaoResponse,
)
from app.modules.indicadores.service import (
    IndicadoresAvaliacoesService,
    IndicadoresGeraisService,
    IndicadoresParticipacaoService,
)
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.get(
    "/gerais",
    response_model=IndicadoresGeraisResponse,
    summary="Consultar indicadores gerais consolidados (Visão Geral / Bloco A)",
)
def obter_indicadores_gerais(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None, ge=2000, le=2100),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> IndicadoresGeraisResponse:
    return IndicadoresGeraisService.calcular_indicadores_gerais(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
    )


@router.get(
    "/avaliacoes",
    response_model=IndicadoresAvaliacoesResponse,
    summary="Consultar indicadores de avaliações e Mapa de Acertos (Bloco B)",
)
def obter_indicadores_avaliacoes(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None, ge=2000, le=2100),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    avaliacao_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> IndicadoresAvaliacoesResponse:
    return IndicadoresAvaliacoesService.calcular_indicadores_avaliacoes(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
        avaliacao_id=avaliacao_id,
    )


@router.get(
    "/participacao",
    response_model=IndicadoresParticipacaoResponse,
    summary="Consultar indicadores de participação e entregas de atividades (Bloco C)",
)
def obter_indicadores_participacao(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None, ge=2000, le=2100),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    atividade_id: Optional[uuid.UUID] = Query(default=None),
    data_referencia: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> IndicadoresParticipacaoResponse:
    return IndicadoresParticipacaoService.calcular_indicadores_participacao(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
        atividade_id=atividade_id,
        data_referencia=data_referencia,
    )
