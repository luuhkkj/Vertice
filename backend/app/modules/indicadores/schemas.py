"""
Schemas Pydantic v2 para o módulo de Indicadores (Fase 4):
- Indicadores Gerais (Bloco A / Visão Geral)
- Indicadores de Avaliações (Bloco B / Mapa de Acertos)
- Indicadores de Participação (Bloco C / Atividades e Entregas)
"""

from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field


# ==============================================================================
# 1. INDICADORES GERAIS (VISÃO GERAL / BLOCO A)
# ==============================================================================


class DistribuicaoItemSchema(BaseModel):
    """Item de distribuição de estudantes e métricas por agrupamento (série, turma, turno)."""

    chave: str
    total_estudantes: int
    percentual_estudantes: float
    frequencia_media: Optional[float] = None
    media_geral: Optional[float] = None


class EvolucaoPeriodoGeralSchema(BaseModel):
    """Métricas gerais consolidadas de um período letivo."""

    ano_letivo: int
    periodo_letivo: str
    total_estudantes: int
    frequencia_media: Optional[float] = None
    media_geral: Optional[float] = None


class ComparacaoPeriodoAnteriorSchema(BaseModel):
    """Comparação entre o período atual e o imediatamente anterior no histórico."""

    periodo_atual: str
    periodo_anterior: str
    variacao_frequencia_media: Optional[float] = None
    variacao_media_geral: Optional[float] = None
    variacao_total_estudantes: int = 0


class FaixaRiscoResumoSchema(BaseModel):
    """Resumo de faixa de risco quando houver previsões válidas disponíveis."""

    faixa: str
    quantidade: int
    percentual: float


class IndicadoresGeraisResponse(BaseModel):
    """Resposta consolidada de Indicadores Gerais (Visão Geral)."""

    total_estudantes_distintos: int = 0
    total_registros_boletim: int = 0
    frequencia_media: Optional[float] = None
    media_geral: Optional[float] = None
    distribuicao_por_serie: list[DistribuicaoItemSchema] = []
    distribuicao_por_turma: list[DistribuicaoItemSchema] = []
    distribuicao_por_turno: list[DistribuicaoItemSchema] = []
    evolucao_por_periodo: list[EvolucaoPeriodoGeralSchema] = []
    comparacao_periodo_anterior: Optional[ComparacaoPeriodoAnteriorSchema] = None
    possui_previsoes_risco: bool = False
    distribuicao_faixas_risco: list[FaixaRiscoResumoSchema] = []
    modelo_nome_vigente: Optional[str] = None
    modelo_versao_vigente: Optional[str] = None
    ultima_previsao_em: Optional[datetime] = None
    nota_metodologica_risco: Optional[str] = None


# ==============================================================================
# 2. INDICADORES DE AVALIAÇÕES (MAPA DE ACERTOS / BLOCO B)
# ==============================================================================


class IndicadorQuestaoSchema(BaseModel):
    """Indicadores detalhados de uma questão de avaliação."""

    questao_id: uuid.UUID
    avaliacao_id: uuid.UUID
    avaliacao_codigo: str
    avaliacao_titulo: Optional[str] = None
    periodo_letivo: Optional[str] = None
    turma_id: Optional[uuid.UUID] = None
    turma_nome: Optional[str] = None
    disciplina_id: Optional[uuid.UUID] = None
    disciplina_codigo: Optional[str] = None
    disciplina_nome: Optional[str] = None
    codigo_questao: str
    tipo_questao: str
    alternativa_correta: Optional[str] = None
    valor_questao: float
    topico: Optional[str] = None
    faixa_dificuldade_cadastrada: str
    faixa_desempenho_observada: Optional[str] = Field(
        default=None,
        description=(
            "Classificação observada da questão pela taxa de acerto: "
            "Fácil (>= 75%), Adequada (50% a < 75%), Atenção (30% a < 50%), Difícil (< 30%)."
        ),
    )
    total_respostas_esperadas: int
    total_respostas_registradas: int
    quantidade_respostas_ausentes: int = 0
    quantidade_acertos: int
    quantidade_erros: int
    quantidade_em_branco: int
    taxa_acerto_percentual: Optional[float] = None
    media_nota_questao: Optional[float] = None
    distribuicao_alternativas: dict[str, int] = {}


class DistribuicaoAcertosAvaliacaoSchema(BaseModel):
    """Distribuição geral de acertos por estudante em uma avaliação (Gráfico 5)."""

    quantidade_acertos: int
    total_questoes_avaliacao: int
    percentual_acerto_estudante: float
    quantidade_estudantes: int
    percentual_estudantes: float


class IndicadorTopicoAvaliacaoSchema(BaseModel):
    """Desempenho agregado por tópico ou habilidade avaliada."""

    topico: str
    total_questoes: int
    total_respostas_esperadas: int
    quantidade_acertos: int
    taxa_acerto_percentual: Optional[float] = None


class DesempenhoTurmaDisciplinaAvaliacaoSchema(BaseModel):
    """Desempenho consolidado por turma e disciplina nas avaliações do recorte."""

    turma_id: uuid.UUID
    turma_nome: str
    disciplina_id: uuid.UUID
    disciplina_codigo: str
    disciplina_nome: str
    total_avaliacoes: int
    media_avaliacoes: Optional[float] = None
    taxa_acerto_media_percentual: Optional[float] = None


class IndicadoresAvaliacoesResponse(BaseModel):
    """Resposta consolidada de Indicadores de Avaliações (Mapa de Acertos)."""

    total_avaliacoes: int = 0
    total_questoes: int = 0
    total_respostas_esperadas: int = 0
    total_respostas_registradas: int = 0
    total_respostas_ausentes: int = 0
    total_acertos: int = 0
    total_erros: int = 0
    total_em_branco: int = 0
    taxa_acerto_geral_percentual: Optional[float] = None
    media_avaliacao_ponderada: Optional[float] = Field(
        default=None,
        description="Média da avaliação na escala 0-10 considerando os pesos (valores) das questões.",
    )
    soma_pesos_avaliacao: Optional[float] = None
    media_pontos_obtidos: Optional[float] = None
    questao_maior_taxa_acerto: Optional[IndicadorQuestaoSchema] = None
    questao_menor_taxa_acerto: Optional[IndicadorQuestaoSchema] = None
    questoes: list[IndicadorQuestaoSchema] = []
    distribuicao_acertos_estudantes: list[DistribuicaoAcertosAvaliacaoSchema] = []
    distribuicao_por_topico: list[IndicadorTopicoAvaliacaoSchema] = []
    desempenho_por_turma_disciplina: list[
        DesempenhoTurmaDisciplinaAvaliacaoSchema
    ] = []


# ==============================================================================
# 3. INDICADORES DE PARTICIPAÇÃO (ATIVIDADES E ENTREGAS / BLOCO C)
# ==============================================================================


class TaxaEntregaAtividadeSchema(BaseModel):
    """Indicadores de entrega para uma atividade específica."""

    atividade_id: uuid.UUID
    codigo: str
    titulo: str
    turma_id: uuid.UUID
    turma_nome: str
    disciplina_id: uuid.UUID
    disciplina_codigo: str
    periodo_letivo: str
    data_limite: date
    total_entregas_esperadas: int
    entregas_realizadas: int
    entregas_no_prazo: int
    entregas_atrasadas: int
    nao_entregas_apos_prazo: int
    pendentes_antes_prazo: int
    taxa_entrega_percentual: Optional[float] = None
    media_notas_disponiveis: Optional[float] = None


class TaxaEntregaTurmaSchema(BaseModel):
    """Taxa consolidada de entregas por turma."""

    turma_id: uuid.UUID
    turma_nome: str
    total_atividades: int
    total_entregas_esperadas: int
    entregas_realizadas: int
    entregas_atrasadas: int
    nao_entregas_apos_prazo: int
    pendentes_antes_prazo: int
    taxa_entrega_percentual: Optional[float] = None
    media_notas_disponiveis: Optional[float] = None


class PercentualIndividualEntregaSchema(BaseModel):
    """Percentual individual de atividades entregues por estudante anonimizado."""

    estudante_id: uuid.UUID
    codigo_anonimo: str
    total_atividades_esperadas: int
    entregas_realizadas: int
    entregas_atrasadas: int
    nao_entregas_apos_prazo: int
    pendentes_antes_prazo: int
    percentual_entregue: Optional[float] = None
    media_notas_disponiveis: Optional[float] = None


class EvolucaoParticipacaoItemSchema(BaseModel):
    """Evolução temporal da participação por período letivo e data limite."""

    periodo_letivo: str
    data_referencia: Optional[date] = None
    total_atividades: int
    total_entregas_esperadas: int
    entregas_realizadas: int
    taxa_entrega_percentual: Optional[float] = None


class IndicadoresParticipacaoResponse(BaseModel):
    """Resposta consolidada de Indicadores de Participação (Bloco C)."""

    total_atividades: int = 0
    total_entregas_esperadas: int = 0
    entregas_realizadas: int = 0
    entregas_no_prazo: int = 0
    entregas_atrasadas: int = 0
    nao_entregas_apos_prazo: int = 0
    atividades_pendentes_antes_prazo: int = 0
    taxa_entrega_geral_percentual: Optional[float] = None
    media_notas_disponiveis: Optional[float] = None
    taxa_por_atividade: list[TaxaEntregaAtividadeSchema] = []
    taxa_por_turma: list[TaxaEntregaTurmaSchema] = []
    percentual_por_estudante: list[PercentualIndividualEntregaSchema] = []
    evolucao_participacao: list[EvolucaoParticipacaoItemSchema] = []

