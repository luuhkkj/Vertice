"""
Schemas Pydantic para o módulo de Integração Preditiva (Fase 7).
"""

from datetime import datetime, timezone
import math
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.integrations.prediction.leakage import (
    MetadadoTecnicoContrato,
    VariavelPreditivaContrato,
)
from app.integrations.prediction.models import FaixaRisco, TipoPrevisao

AVISO_METODOLOGICO_PADRAO = (
    "Previsão probabilística gerada por modelo externo versionado. "
    "Não representa diagnóstico definitivo nem substitui avaliação pedagógica; "
    "métricas observadas de frequência, notas e entregas continuam registradas separadamente."
)


class ModeloPreditivoDisponivelResponse(BaseModel):
    """Metadados de modelo preditivo descoberto centralmente para seleção e execução."""

    modelo_nome: str
    nome_exibicao: str
    modelo_versao: str
    artefato_relativo: str
    tipo_previsao: str
    politica_classificacao_versao: str
    disponivel_inferencia: bool
    motivo_indisponibilidade: Optional[str] = None


class CredencialIntegracaoCreate(BaseModel):
    """Solicitação administrativa para emitir credencial técnica de integração preditiva."""

    nome: str = Field(..., min_length=3, max_length=120)
    escola_id: Optional[uuid.UUID] = None
    modelo_autorizado: Optional[str] = Field(default=None, min_length=2, max_length=100)
    modelos_permitidos: Optional[list[str]] = None
    permite_leitura_inferencia: Optional[bool] = None
    expira_em: Optional[datetime] = None

    @field_validator("nome")
    @classmethod
    def _strip_nome(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Nome da credencial deve ter ao menos 3 caracteres.")
        return s

    @field_validator("modelo_autorizado")
    @classmethod
    def _strip_modelo_autorizado(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("`modelo_autorizado` não pode ser vazio.")
        return s

    @field_validator("modelos_permitidos")
    @classmethod
    def _normalizar_modelos(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        limpos = [m.strip() for m in v if isinstance(m, str) and m.strip()]
        if not limpos:
            raise ValueError(
                "Se `modelos_permitidos` for informado, informe ao menos um nome de modelo válido."
            )
        return list(dict.fromkeys(limpos))

    @model_validator(mode="after")
    def _conciliar_modelo_e_escopo(self) -> "CredencialIntegracaoCreate":
        informou_modelo_autorizado = self.modelo_autorizado is not None
        if informou_modelo_autorizado:
            if (
                self.modelos_permitidos is not None
                and self.modelos_permitidos != [self.modelo_autorizado]
            ):
                raise ValueError(
                    "`modelo_autorizado` e `modelos_permitidos` possuem valores conflitantes."
                )
            self.modelos_permitidos = [self.modelo_autorizado]
        elif (
            self.permite_leitura_inferencia is True
            and self.modelos_permitidos
            and len(self.modelos_permitidos) == 1
        ):
            self.modelo_autorizado = self.modelos_permitidos[0]

        if self.permite_leitura_inferencia is None:
            self.permite_leitura_inferencia = bool(
                self.escola_id is not None and informou_modelo_autorizado
            )

        if self.permite_leitura_inferencia:
            if self.escola_id is None:
                raise ValueError(
                    "Credenciais autorizadas a exportar dados para inferência devem estar "
                    "vinculadas a uma unidade escolar específica (`escola_id`)."
                )
            if not self.modelos_permitidos or len(self.modelos_permitidos) != 1:
                raise ValueError(
                    "Credenciais autorizadas a exportar dados para inferência exigem a "
                    "seleção de exatamente um modelo autorizado."
                )
        return self


class CredencialIntegracaoResponse(BaseModel):
    """Representação pública/administrativa de uma credencial técnica (sem segredo)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    prefixo_chave: str
    escola_id: Optional[uuid.UUID]
    modelo_autorizado: Optional[str] = None
    modelos_permitidos: Optional[list[str]]
    permite_leitura_inferencia: bool = False
    criado_por_usuario_id: uuid.UUID
    ativo: bool
    expira_em: Optional[datetime]
    ultimo_uso_em: Optional[datetime]
    criado_em: datetime
    atualizado_em: datetime

    @model_validator(mode="after")
    def _preencher_modelo_autorizado(self) -> "CredencialIntegracaoResponse":
        if (
            self.modelo_autorizado is None
            and self.modelos_permitidos
            and len(self.modelos_permitidos) == 1
        ):
            self.modelo_autorizado = self.modelos_permitidos[0]
        return self


class CredencialIntegracaoCriadaResponse(CredencialIntegracaoResponse):
    """Resposta retornada exclusivamente no momento da criação da credencial."""

    chave_secreta: str


class ValidarVariaveisRequest(BaseModel):
    """Payload para inspeção preventiva de variáveis contra vazamento de dados."""

    variaveis: list[str] | dict[str, Any]
    campos_proibidos_extras: Optional[list[str] | dict[str, str]] = None
    catalogo_extensao: Optional[list[VariavelPreditivaContrato | dict[str, Any]]] = None


class CatalogoVariaveisResponse(BaseModel):
    """Contrato oficial de variáveis elegíveis, metadados e política anti-leakage do Vértice."""

    politica_anti_leakage_ativa: bool = True
    exige_contrato_para_desconhecidas: bool = True
    campos_proibidos_base: dict[str, str]
    variaveis_elegiveis: list[VariavelPreditivaContrato]
    alvo_supervisionado_reservado: VariavelPreditivaContrato
    metadados_tecnicos_permitidos: list[MetadadoTecnicoContrato]


class PrevisaoRecebimentoItem(BaseModel):
    """Contrato de recebimento unitário de previsão externa de risco."""

    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = Field(default=None, min_length=1, max_length=50)
    escola_id: Optional[uuid.UUID] = None
    turma_id: Optional[uuid.UUID] = None
    ano_letivo: int = Field(..., ge=2000, le=2100)
    periodo_letivo: str = Field(..., min_length=1, max_length=30)
    tipo_previsao: TipoPrevisao = TipoPrevisao.EVASAO
    pontuacao_risco: float = Field(..., ge=0.0, le=1.0)
    faixa_risco: FaixaRisco
    politica_classificacao_versao: Optional[str] = Field(default=None, max_length=60)
    modelo_nome: str = Field(..., min_length=2, max_length=100)
    modelo_versao: str = Field(..., min_length=1, max_length=50)
    gerado_em: datetime
    lote_externo_id: Optional[str] = Field(default=None, max_length=120)
    variaveis_utilizadas: Optional[list[str] | dict[str, Any]] = None
    metadados_tecnicos: Optional[dict[str, Any]] = None

    @field_validator("pontuacao_risco")
    @classmethod
    def _validar_pontuacao(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("`pontuacao_risco` deve ser um número finito entre 0.0 e 1.0.")
        if v < 0.0 or v > 1.0:
            raise ValueError("`pontuacao_risco` deve estar no intervalo [0.0, 1.0].")
        return round(float(v), 6)

    @field_validator("periodo_letivo", "modelo_nome", "modelo_versao")
    @classmethod
    def _strip_obrigatorio(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Campo textual obrigatório não pode ser vazio.")
        return s

    @field_validator("codigo_anonimo", "politica_classificacao_versao", "lote_externo_id")
    @classmethod
    def _strip_opcional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("gerado_em")
    @classmethod
    def _normalizar_gerado_em(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validar_identificacao_estudante(self) -> "PrevisaoRecebimentoItem":
        if self.estudante_id is None and self.codigo_anonimo is None:
            raise ValueError(
                "Informe `estudante_id` ou (`codigo_anonimo` e `escola_id`) para identificar o estudante."
            )
        if self.estudante_id is None and self.escola_id is None:
            raise ValueError(
                "Quando `estudante_id` não for informado, `escola_id` é obrigatório junto de `codigo_anonimo`."
            )
        return self


class PrevisaoRecebimentoLoteRequest(BaseModel):
    """Lote atômico de previsões de risco enviadas por serviço de ML autorizado."""

    lote_externo_id: Optional[str] = Field(default=None, max_length=120)
    itens: list[PrevisaoRecebimentoItem] = Field(..., min_length=1, max_length=2000)

    @field_validator("lote_externo_id")
    @classmethod
    def _strip_lote(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip() or None


class PrevisaoResponse(BaseModel):
    """Previsão de risco persistida, vinculada a estudante anonimizado e modelo versionado."""

    id: uuid.UUID
    estudante_id: uuid.UUID
    codigo_anonimo: Optional[str] = None
    escola_id: uuid.UUID
    turma_id: Optional[uuid.UUID] = None
    turma_nome: Optional[str] = None
    ano_letivo: int
    periodo_letivo: str
    tipo_previsao: TipoPrevisao
    pontuacao_risco: float
    faixa_risco: FaixaRisco
    politica_classificacao_versao: Optional[str] = None
    modelo_nome: str
    modelo_versao: str
    gerado_em: datetime
    recebido_em: datetime
    lote_externo_id: Optional[str] = None
    assinatura_idempotencia: str
    metadados_tecnicos: Optional[dict[str, Any]] = None
    aviso_metodologico: str = AVISO_METODOLOGICO_PADRAO


class PrevisaoLoteResponse(BaseModel):
    """Resultado consolidado de ingestão em lote de previsões."""

    quantidade_recebida: int
    lote_externo_id: Optional[str] = None
    itens: list[PrevisaoResponse]


class HistoricoPrevisoesEstudanteResponse(BaseModel):
    """Série histórica append-only das previsões de um estudante anonimizado."""

    estudante_id: uuid.UUID
    codigo_anonimo: str
    escola_id: uuid.UUID
    total_previsoes: int
    previsao_mais_recente: Optional[PrevisaoResponse] = None
    historico: list[PrevisaoResponse] = []
    aviso_metodologico: str = AVISO_METODOLOGICO_PADRAO


class FaixaDistribuicaoPrevisaoSchema(BaseModel):
    """Distribuição quantitativa e percentual de uma faixa de risco."""

    faixa: str
    quantidade: int
    percentual: float


class VersaoModeloDisponivelSchema(BaseModel):
    """Identificador de uma versão de modelo com previsões no escopo."""

    modelo_nome: str
    modelo_versao: str
    tipo_previsao: str
    total_registros: int
    ultima_previsao_em: datetime


class ResumoPrevisoesRiscoResponse(BaseModel):
    """
    Resumo agregado de risco preditivo no escopo autorizado do usuário.
    Segue política explícita de versão única para nunca misturar versões distintas na contagem.
    """

    possui_previsoes: bool = False
    total_previsoes_registradas: int = 0
    total_estudantes_avaliados: int = 0
    modelo_nome_vigente: Optional[str] = None
    modelo_versao_vigente: Optional[str] = None
    ultima_previsao_em: Optional[datetime] = None
    politica_selecao_versao: str = (
        "Quando `modelo_versao` não é especificado, seleciona automaticamente a versão mais recente "
        "no escopo autorizado e considera a última previsão gerada por estudante nessa versão."
    )
    distribuicao_faixas: list[FaixaDistribuicaoPrevisaoSchema] = []
    versoes_disponiveis: list[VersaoModeloDisponivelSchema] = []
    aviso_metodologico: str = AVISO_METODOLOGICO_PADRAO


class ItemExportacaoInferenciaSchema(BaseModel):
    """
    Registro anonimizado mínimo exportado exclusivamente para inferência no corte
    do primeiro período. Não inclui PII nem variáveis pós-corte.
    """

    model_config = ConfigDict(extra="forbid")

    estudante_id: uuid.UUID
    escola_id: uuid.UUID
    turma_id: uuid.UUID
    ano_letivo: int = Field(..., ge=2000, le=2100)
    periodo_letivo: str = Field(..., min_length=1, max_length=30)
    idade: Optional[int] = Field(default=None, ge=10, le=100)
    historico_reprovacoes: Optional[int] = Field(default=None, ge=0, le=50)
    nota_t1: Optional[float] = Field(default=None, ge=0.0, le=10.0)


class ExportacaoInferenciaResponse(BaseModel):
    """Resposta paginada da rota controlada de extração e descoberta de configuração ML."""

    escola_id: uuid.UUID
    credencial_nome: str
    modelo_nome: str
    modelo_versao: Optional[str] = None
    artefato_relativo: Optional[str] = None
    tipo_previsao: str = "RISCO_ACADEMICO"
    periodo_letivo: str
    ano_letivo: Optional[int] = None
    turma_id: Optional[uuid.UUID] = None
    disciplina_id: Optional[uuid.UUID] = None
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    itens: list[ItemExportacaoInferenciaSchema] = []
