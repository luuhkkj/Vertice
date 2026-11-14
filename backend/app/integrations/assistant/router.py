"""
Roteador FastAPI para o módulo do Assistente Inteligente e Contexto IA (Fase 7).
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.integrations.assistant.models import ResultadoAutorizacaoIA
from app.integrations.assistant.schemas import (
    AuditoriaConsultaIAResponse,
    ContextoAssistenteEstruturado,
    RespostaAssistenteLLM,
    SolicitacaoContextoAssistente,
    StatusAssistenteResponse,
)
from app.integrations.assistant.service import AssistenteContextoService
from app.modules.usuarios.models import Usuario

router = APIRouter()


class ConsultaAssistentePromptRequest(SolicitacaoContextoAssistente):
    """Solicitação combinada de contexto e pergunta para futura conexão LLM."""

    pergunta_usuario: str = Field(..., min_length=2, max_length=2000)


@router.get(
    "/status",
    response_model=StatusAssistenteResponse,
    summary="Consultar prontidão e estado arquitetural do Assistente IA",
)
def obter_status_assistente(
    current_user: Usuario = Depends(get_current_user),
) -> StatusAssistenteResponse:
    _ = current_user
    return AssistenteContextoService.obter_status()


@router.post(
    "/contexto",
    response_model=ContextoAssistenteEstruturado,
    summary="Construir contexto educacional estruturado, autorizado e auditado para IA",
)
def construir_contexto_assistente(
    dados: SolicitacaoContextoAssistente,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> ContextoAssistenteEstruturado:
    return AssistenteContextoService.construir_contexto_autorizado(
        db=db,
        solicitacao=dados,
        usuario=current_user,
    )


@router.post(
    "/consultar",
    response_model=RespostaAssistenteLLM,
    summary="Executar consulta via provedor LLM desacoplado (retorna 503 enquanto provedor não conectado)",
)
def consultar_assistente_llm(
    dados: ConsultaAssistentePromptRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> RespostaAssistenteLLM:
    return AssistenteContextoService.consultar_com_provedor(
        db=db,
        solicitacao=dados,
        pergunta_usuario=dados.pergunta_usuario,
        usuario=current_user,
    )


@router.get(
    "/auditoria",
    response_model=list[AuditoriaConsultaIAResponse],
    summary="Listar registros de auditoria das solicitações de contexto ao Assistente IA",
)
def listar_auditoria_assistente(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    resultado_autorizacao: Optional[ResultadoAutorizacaoIA] = Query(default=None),
    request_id: Optional[uuid.UUID] = Query(default=None),
    conversation_id: Optional[uuid.UUID] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> list[AuditoriaConsultaIAResponse]:
    return AssistenteContextoService.listar_auditoria(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        resultado_autorizacao=resultado_autorizacao,
        request_id=request_id,
        conversation_id=conversation_id,
        skip=skip,
        limit=limit,
    )
