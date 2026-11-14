"""
Schemas Pydantic para o módulo do Assistente Inteligente / Contexto IA (Fase 7).
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.integrations.assistant.models import (
    ResultadoAutorizacaoIA,
    TipoContextoAssistente,
)
from app.integrations.prediction.schemas import (
    HistoricoPrevisoesEstudanteResponse,
    ResumoPrevisoesRiscoResponse,
)
from app.modules.acompanhamento.schemas import AcompanhamentoResponse
from app.modules.estudantes.schemas import EstudanteHistoricoDetalhadoResponse
from app.modules.indicadores.schemas import (
    IndicadoresAvaliacoesResponse,
    IndicadoresGeraisResponse,
    IndicadoresParticipacaoResponse,
)


class SolicitacaoContextoAssistente(BaseModel):
    """Parâmetros tipados para montagem segura de contexto pedagógico para IA."""

    tipo_contexto: TipoContextoAssistente
    escola_id: Optional[uuid.UUID] = None
    turma_id: Optional[uuid.UUID] = None
    disciplina_id: Optional[uuid.UUID] = None
    estudante_id: Optional[uuid.UUID] = None
    ano_letivo: Optional[int] = Field(default=None, ge=2000, le=2100)
    periodo_letivo: Optional[str] = Field(default=None, max_length=30)
    modelo_nome: Optional[str] = Field(default=None, max_length=100)
    modelo_versao: Optional[str] = Field(default=None, max_length=50)
    incluir_acompanhamentos: bool = True
    conversation_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _validar_alvo_por_tipo(self) -> "SolicitacaoContextoAssistente":
        if self.tipo_contexto == TipoContextoAssistente.TURMA and self.turma_id is None:
            raise ValueError(
                "Contexto `TURMA` exige o parâmetro obrigatório `turma_id`."
            )
        if (
            self.tipo_contexto == TipoContextoAssistente.INDIVIDUAL
            and self.estudante_id is None
        ):
            raise ValueError(
                "Contexto `INDIVIDUAL` exige o parâmetro obrigatório `estudante_id`."
            )
        return self


class MetadadosContextoAssistente(BaseModel):
    """Metadados de rastreabilidade e privacidade do pacote de contexto montado."""

    auditoria_id: uuid.UUID
    request_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    gerado_em: datetime
    tipo_contexto: TipoContextoAssistente
    usuario_papel: str
    escola_id: Optional[uuid.UUID] = None
    turma_id: Optional[uuid.UUID] = None
    disciplina_id: Optional[uuid.UUID] = None
    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = None
    ano_letivo: Optional[int] = None
    periodo_letivo: Optional[str] = None
    anonimizacao_ativa: bool = True
    garantias_privacidade: list[str]
    fontes_utilizadas: list[str]


class ContextoAssistenteEstruturado(BaseModel):
    """
    Pacote padronizado e autorizado de contexto educacional pronto para uso por um
    futuro provedor LLM, reutilizando estritamente os serviços reais do Vértice.
    """

    metadados: MetadadosContextoAssistente
    escopo_pedagogico: dict[str, Any]
    indicadores_gerais: Optional[IndicadoresGeraisResponse] = None
    indicadores_avaliacoes: Optional[IndicadoresAvaliacoesResponse] = None
    indicadores_participacao: Optional[IndicadoresParticipacaoResponse] = None
    resumo_previsoes_risco: Optional[ResumoPrevisoesRiscoResponse] = None
    estudante_historico: Optional[EstudanteHistoricoDetalhadoResponse] = None
    previsoes_estudante: Optional[HistoricoPrevisoesEstudanteResponse] = None
    acompanhamentos_recentes: list[AcompanhamentoResponse] = []
    diretrizes_interpretacao: list[str]


class AuditoriaConsultaIAResponse(BaseModel):
    """Registro de auditoria de tentativa ou emissão de contexto para IA."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    usuario_id: uuid.UUID
    papel_usuario: str
    escola_id_solicitada: Optional[uuid.UUID]
    turma_id_solicitada: Optional[uuid.UUID]
    estudante_id_solicitado: Optional[uuid.UUID]
    tipo_contexto: TipoContextoAssistente
    resultado_autorizacao: ResultadoAutorizacaoIA
    motivo_decisao: str
    filtros_utilizados: Optional[dict[str, Any]]
    resumo_fontes_consultadas: Optional[list[str]]
    criado_em: datetime


class StatusAssistenteResponse(BaseModel):
    """Estado arquitetural da camada de assistente inteligente no backend."""

    provedor_llm_configurado: bool = False
    provedor_nome: str
    modo_operacao: str
    niveis_contexto_suportados: list[str]
    auditoria_ativa: bool = True
    mensagem: str


class MensagemConversaLLM(BaseModel):
    """Contrato de mensagem para futura integração com provedores LLM."""

    papel: str = Field(..., pattern="^(system|user|assistant)$")
    conteudo: str = Field(..., min_length=1, max_length=8000)


class RequisicaoAssistenteLLM(BaseModel):
    """Contrato abstrato de entrada para futura invocação de provedor LLM."""

    pergunta_usuario: str = Field(..., min_length=2, max_length=2000)
    contexto: ContextoAssistenteEstruturado
    historico_mensagens: list[MensagemConversaLLM] = []


class RespostaAssistenteLLM(BaseModel):
    """Contrato abstrato de resposta estruturada de um futuro provedor LLM."""

    provedor: str
    modelo: Optional[str] = None
    resposta_texto: str
    auditoria_id: uuid.UUID
    request_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    citacoes_fontes: list[str] = []
    aviso_responsavel: str
