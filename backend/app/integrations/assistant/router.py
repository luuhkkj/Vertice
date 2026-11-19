"""
Roteador FastAPI para o módulo do Assistente Inteligente e Contexto IA (Fase 7).
"""

from typing import Optional
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.integrations.assistant.documents import (
    MAX_ARQUIVOS_ASSISTENTE,
    MAX_BYTES_ARQUIVO_ASSISTENTE,
    MAX_BYTES_TOTAL_ASSISTENTE,
    extrair_documentos_assistente,
)
from app.integrations.assistant.models import ResultadoAutorizacaoIA
from app.integrations.assistant.schemas import (
    AuditoriaConsultaIAResponse,
    ContextoAssistenteEstruturado,
    MensagemConversaLLM,
    RespostaAssistenteLLM,
    SolicitacaoContextoAssistente,
    StatusAssistenteResponse,
)
from app.integrations.assistant.service import AssistenteContextoService
from app.modules.usuarios.models import Usuario

router = APIRouter()


class ConsultaAssistentePromptRequest(SolicitacaoContextoAssistente):
    """Solicitação combinada de contexto, pergunta e histórico da conversa."""

    pergunta_usuario: str = Field(..., min_length=2, max_length=2000)
    historico_mensagens: list[MensagemConversaLLM] = Field(
        default_factory=list,
        max_length=12,
    )


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
    summary="Responder com contexto autorizado usando Ollama local",
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
        historico_mensagens=dados.historico_mensagens,
    )


@router.post(
    "/consultar-arquivos",
    response_model=RespostaAssistenteLLM,
    summary="Responder com contexto autorizado e arquivos de texto",
)
def consultar_assistente_com_arquivos(
    dados_json: str = Form(...),
    arquivos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> RespostaAssistenteLLM:
    try:
        dados = ConsultaAssistentePromptRequest.model_validate_json(dados_json)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Os dados da consulta enviados junto aos arquivos são inválidos.",
        ) from exc

    if not arquivos or len(arquivos) > MAX_ARQUIVOS_ASSISTENTE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Envie de 1 a {MAX_ARQUIVOS_ASSISTENTE} arquivos por consulta.",
        )

    entradas: list[tuple[str, bytes]] = []
    total_bytes = 0
    try:
        for arquivo in arquivos:
            conteudo = arquivo.file.read(MAX_BYTES_ARQUIVO_ASSISTENTE + 1)
            if len(conteudo) > MAX_BYTES_ARQUIVO_ASSISTENTE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"O arquivo {arquivo.filename or 'enviado'} "
                        "excede o limite de 5 MB."
                    ),
                )
            total_bytes += len(conteudo)
            if total_bytes > MAX_BYTES_TOTAL_ASSISTENTE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="O tamanho total dos anexos excede 10 MB.",
                )
            entradas.append((arquivo.filename or "", conteudo))
    finally:
        for arquivo in arquivos:
            arquivo.file.close()

    documentos = extrair_documentos_assistente(entradas)
    return AssistenteContextoService.consultar_com_provedor(
        db=db,
        solicitacao=dados,
        pergunta_usuario=dados.pergunta_usuario,
        usuario=current_user,
        historico_mensagens=dados.historico_mensagens,
        documentos_anexados=documentos,
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
