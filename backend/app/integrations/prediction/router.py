"""
Roteador FastAPI para o módulo de Integração Preditiva (Fase 7).

Separa estritamente:
- Gestão de credenciais de serviço (ADMINISTRADOR).
- Ingestão de previsões unitárias e em lote (exclusiva para credencial técnica `X-Service-Token`).
- Consultas e resumos de risco (exclusivos para perfis pedagógicos no próprio escopo).
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    require_acesso_pedagogico,
    require_admin,
)
from app.database.connection import get_db
from app.integrations.prediction.leakage import ResultadoValidacaoLeakage
from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    FaixaRisco,
    TipoPrevisao,
)
from app.integrations.prediction.schemas import (
    CatalogoVariaveisResponse,
    CredencialIntegracaoCreate,
    CredencialIntegracaoCriadaResponse,
    CredencialIntegracaoResponse,
    HistoricoPrevisoesEstudanteResponse,
    PrevisaoLoteResponse,
    PrevisaoRecebimentoItem,
    PrevisaoRecebimentoLoteRequest,
    PrevisaoResponse,
    ResumoPrevisoesRiscoResponse,
    ValidarVariaveisRequest,
)
from app.integrations.prediction.service import PredictionService
from app.modules.usuarios.models import Usuario

router = APIRouter()


def get_credencial_integracao_predicao(
    x_service_token: Optional[str] = Header(default=None, alias="X-Service-Token"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> CredencialIntegracaoPredicao:
    """
    Dependência exclusiva de autenticação de serviço externo de predição.
    Rejeita explicitamente tokens comuns de usuário (JWT) com HTTP 403.
    """
    token_bruto = x_service_token
    if not token_bruto and authorization:
        partes = authorization.strip().split(" ", 1)
        if len(partes) == 2 and partes[0].lower() == "bearer":
            token_bruto = partes[1]
        else:
            token_bruto = authorization.strip()
    return PredictionService.autenticar_credencial_servico(db=db, token_bruto=token_bruto)


# ==============================================================================
# Credenciais técnicas de serviço (Administrativo)
# ==============================================================================
@router.post(
    "/credenciais",
    response_model=CredencialIntegracaoCriadaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Emitir credencial técnica de envio de previsões (somente Administrador)",
)
def criar_credencial_integracao(
    dados: CredencialIntegracaoCreate,
    db: Session = Depends(get_db),
    admin_user: Usuario = Depends(require_admin),
) -> CredencialIntegracaoCriadaResponse:
    return PredictionService.criar_credencial_integracao(
        db=db,
        dados=dados,
        usuario_admin=admin_user,
    )


@router.get(
    "/credenciais",
    response_model=list[CredencialIntegracaoResponse],
    summary="Listar credenciais técnicas de integração preditiva (somente Administrador)",
)
def listar_credenciais_integracao(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    apenas_ativas: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    admin_user: Usuario = Depends(require_admin),
) -> list[CredencialIntegracaoResponse]:
    return PredictionService.listar_credenciais_integracao(
        db=db,
        usuario_admin=admin_user,
        escola_id=escola_id,
        apenas_ativas=apenas_ativas,
    )


@router.patch(
    "/credenciais/{credencial_id}/revogar",
    response_model=CredencialIntegracaoResponse,
    summary="Revogar credencial técnica de integração preditiva (somente Administrador)",
)
def revogar_credencial_integracao(
    credencial_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin_user: Usuario = Depends(require_admin),
) -> CredencialIntegracaoResponse:
    return PredictionService.revogar_credencial_integracao(
        db=db,
        credencial_id=credencial_id,
        usuario_admin=admin_user,
    )


# ==============================================================================
# Contrato formal de variáveis e validação anti-leakage
# ==============================================================================
@router.get(
    "/contrato-variaveis",
    response_model=CatalogoVariaveisResponse,
    summary="Consultar catálogo de variáveis elegíveis e política anti-data-leakage",
)
def obter_contrato_variaveis(
    current_user: Usuario = Depends(get_current_user),
) -> CatalogoVariaveisResponse:
    _ = current_user
    return PredictionService.obter_catalogo_variaveis()


@router.post(
    "/validar-variaveis",
    response_model=ResultadoValidacaoLeakage,
    summary="Validar lista ou dicionário de variáveis quanto a risco de Data Leakage / PII",
)
def validar_variaveis_entrada(
    dados: ValidarVariaveisRequest,
    current_user: Usuario = Depends(get_current_user),
) -> ResultadoValidacaoLeakage:
    _ = current_user
    return PredictionService.inspecionar_variaveis_entrada(dados)


# ==============================================================================
# Ingestão de previsões externas (Credencial técnica dedicada)
# ==============================================================================
@router.post(
    "/lote",
    response_model=PrevisaoLoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar lote atômico de previsões de risco (credencial de serviço ML)",
)
def registrar_lote_previsoes(
    dados: PrevisaoRecebimentoLoteRequest,
    db: Session = Depends(get_db),
    credencial: CredencialIntegracaoPredicao = Depends(
        get_credencial_integracao_predicao
    ),
) -> PrevisaoLoteResponse:
    return PredictionService.registrar_lote_previsoes(
        db=db,
        dados=dados,
        credencial=credencial,
    )


@router.post(
    "",
    response_model=PrevisaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar previsão individual de risco (credencial de serviço ML)",
)
def registrar_previsao_individual(
    dados: PrevisaoRecebimentoItem,
    db: Session = Depends(get_db),
    credencial: CredencialIntegracaoPredicao = Depends(
        get_credencial_integracao_predicao
    ),
) -> PrevisaoResponse:
    return PredictionService.registrar_previsao_unica(
        db=db,
        item=dados,
        credencial=credencial,
    )


# ==============================================================================
# Consultas pedagógicas escopadas (Gestor / Professor)
# ==============================================================================
@router.get(
    "/resumo",
    response_model=ResumoPrevisoesRiscoResponse,
    summary="Consultar resumo agregado de faixas de risco com política de versão única",
)
def obter_resumo_previsoes(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None, ge=2000, le=2100),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    tipo_previsao: Optional[TipoPrevisao] = Query(default=None),
    modelo_nome: Optional[str] = Query(default=None, max_length=100),
    modelo_versao: Optional[str] = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> ResumoPrevisoesRiscoResponse:
    return PredictionService.obter_resumo_previsoes(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
        tipo_previsao=tipo_previsao,
        modelo_nome=modelo_nome,
        modelo_versao=modelo_versao,
    )


@router.get(
    "/estudantes/{estudante_id}",
    response_model=HistoricoPrevisoesEstudanteResponse,
    summary="Consultar histórico append-only de previsões de risco de um estudante",
)
def obter_historico_previsoes_estudante(
    estudante_id: uuid.UUID,
    tipo_previsao: Optional[TipoPrevisao] = Query(default=None),
    modelo_nome: Optional[str] = Query(default=None, max_length=100),
    modelo_versao: Optional[str] = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> HistoricoPrevisoesEstudanteResponse:
    return PredictionService.obter_historico_estudante(
        db=db,
        estudante_id=estudante_id,
        usuario=current_user,
        tipo_previsao=tipo_previsao,
        modelo_nome=modelo_nome,
        modelo_versao=modelo_versao,
    )


@router.get(
    "",
    response_model=list[PrevisaoResponse],
    summary="Listar previsões de risco no escopo pedagógico autorizado",
)
def listar_previsoes_risco(
    escola_id: Optional[uuid.UUID] = Query(default=None),
    turma_id: Optional[uuid.UUID] = Query(default=None),
    disciplina_id: Optional[uuid.UUID] = Query(default=None),
    ano_letivo: Optional[int] = Query(default=None, ge=2000, le=2100),
    periodo_letivo: Optional[str] = Query(default=None, max_length=30),
    tipo_previsao: Optional[TipoPrevisao] = Query(default=None),
    faixa_risco: Optional[FaixaRisco] = Query(default=None),
    modelo_nome: Optional[str] = Query(default=None, max_length=100),
    modelo_versao: Optional[str] = Query(default=None, max_length=50),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[PrevisaoResponse]:
    return PredictionService.listar_previsoes(
        db=db,
        usuario=current_user,
        escola_id=escola_id,
        turma_id=turma_id,
        disciplina_id=disciplina_id,
        ano_letivo=ano_letivo,
        periodo_letivo=periodo_letivo,
        tipo_previsao=tipo_previsao,
        faixa_risco=faixa_risco,
        modelo_nome=modelo_nome,
        modelo_versao=modelo_versao,
        skip=skip,
        limit=limit,
    )
