"""
Roteador de endpoints para o módulo de Importação de Datasets Escolares (Fase 3).
Utiliza autenticação JWT e a dependência `require_importacao_datasets` (gestor e professor).
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_importacao_datasets
from app.database.connection import get_db
from app.modules.importacao.models import TipoImportacao
from app.modules.importacao.schemas import (
    ConfirmacaoImportacaoResponse,
    LoteImportacaoPreviaResponse,
    LoteImportacaoResumoResponse,
)
from app.modules.importacao.service import ImportacaoService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "/validar",
    response_model=LoteImportacaoPreviaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Etapa 1 — Upload, validação e geração de prévia",
    description=(
        "Recebe um arquivo CSV ou XLSX, identifica automaticamente o usuário autenticado e o tipo de dataset "
        "(`dados_escolares`, `avaliacoes` ou `atividades`), valida o escopo autorizado "
        "(escola do gestor ou vínculo turma+disciplina do professor), verifica regras de anonimização e "
        "retorna o lote e o relatório de validação sem persistir dados acadêmicos."
    ),
)
async def validar_arquivo_importacao(
    arquivo: UploadFile = File(
        ...,
        description="Arquivo CSV ou XLSX com dados escolares, avaliações ou atividades anonimizados (máximo 10 MB).",
    ),
    tipo_importacao: Optional[TipoImportacao] = Query(
        default=None,
        description="Tipo do dataset (opcional; detectado automaticamente pelas colunas quando omitido).",
    ),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> LoteImportacaoPreviaResponse:
    conteudo_bytes = await arquivo.read()
    return ImportacaoService.validar_e_gerar_previa(
        db=db,
        nome_arquivo=arquivo.filename,
        conteudo_bytes=conteudo_bytes,
        usuario_autenticado=current_user,
        tipo_importacao=tipo_importacao,
    )


@router.get(
    "/{lote_id}",
    response_model=LoteImportacaoResumoResponse,
    summary="Consultar status e resumo de um lote de importação",
)
def obter_lote_importacao(
    lote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> LoteImportacaoResumoResponse:
    return ImportacaoService.obter_resumo_lote(
        db=db,
        lote_id=lote_id,
        usuario_autenticado=current_user,
    )


@router.get(
    "/{lote_id}/previa",
    response_model=LoteImportacaoPreviaResponse,
    summary="Consultar prévia e relatório de validação do lote",
)
def obter_previa_lote_importacao(
    lote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> LoteImportacaoPreviaResponse:
    return ImportacaoService.obter_previa_lote(
        db=db,
        lote_id=lote_id,
        usuario_autenticado=current_user,
    )


@router.post(
    "/{lote_id}/confirmar",
    response_model=ConfirmacaoImportacaoResponse,
    status_code=status.HTTP_200_OK,
    summary="Etapa 2 — Confirmar importação e persistir em transação atômica",
    description=(
        "Revalida a identidade, permissões e vínculos atuais do usuário autenticado e "
        "persiste os registros validados em transação atômica (commit integral ou rollback completo)."
    ),
)
def confirmar_lote_importacao(
    lote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> ConfirmacaoImportacaoResponse:
    return ImportacaoService.confirmar_importacao(
        db=db,
        lote_id=lote_id,
        usuario_autenticado=current_user,
    )


@router.post(
    "/{lote_id}/descartar",
    response_model=LoteImportacaoResumoResponse,
    status_code=status.HTTP_200_OK,
    summary="Descartar lote de importação não confirmado",
)
def descartar_lote_importacao(
    lote_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_importacao_datasets),
) -> LoteImportacaoResumoResponse:
    return ImportacaoService.descartar_lote(
        db=db,
        lote_id=lote_id,
        usuario_autenticado=current_user,
    )

