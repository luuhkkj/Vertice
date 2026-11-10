"""
Schemas Pydantic v2 para o módulo de Avaliações, Questões e Respostas (Fase 4).
Nota: `usuario_id` e `escola_id` NUNCA são aceitos no payload de entrada — são derivados
da sessão autenticada e da turma autorizada.
"""

from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.avaliacoes.models import (
    ALTERNATIVAS_VALIDAS_GABARITO,
    ALTERNATIVAS_VALIDAS_RESPOSTA,
    FaixaDificuldadeQuestao,
    StatusAvaliacao,
    TipoQuestao,
)


class AvaliacaoCreate(BaseModel):
    """Dados para criação de uma nova avaliação."""

    codigo: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=60,
        description="Código identificador da avaliação na turma/disciplina (ex: AV-MAT-2026-01). Se omitido, será gerado automaticamente.",
    )
    titulo: str = Field(..., min_length=2, max_length=150)
    turma_id: uuid.UUID
    disciplina_id: uuid.UUID
    periodo_letivo: str = Field(..., min_length=1, max_length=30)
    data_avaliacao: date
    status: StatusAvaliacao = StatusAvaliacao.PUBLICADA


class AvaliacaoUpdate(BaseModel):
    """Dados para atualização parcial de uma avaliação."""

    titulo: Optional[str] = Field(default=None, min_length=2, max_length=150)
    periodo_letivo: Optional[str] = Field(default=None, min_length=1, max_length=30)
    data_avaliacao: Optional[date] = None
    status: Optional[StatusAvaliacao] = None
    ativo: Optional[bool] = None


class QuestaoAvaliacaoCreate(BaseModel):
    """Dados para criação de uma questão vinculada a uma avaliação."""

    codigo_questao: str = Field(..., min_length=1, max_length=30)
    tipo_questao: TipoQuestao
    alternativa_correta: Optional[str] = Field(default=None, max_length=5)
    valor_questao: float = Field(..., gt=0.0, le=100.0)
    faixa_dificuldade: FaixaDificuldadeQuestao = FaixaDificuldadeQuestao.ADEQUADA
    topico: Optional[str] = Field(default=None, max_length=120)

    @field_validator("alternativa_correta")
    @classmethod
    def _normalizar_alternativa(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpa = v.strip().upper()
        if not limpa:
            return None
        if limpa not in ALTERNATIVAS_VALIDAS_GABARITO:
            raise ValueError(
                f"Alternativa correta inválida ('{v}'). Use uma das opções: A, B, C, D ou E."
            )
        return limpa

    @model_validator(mode="after")
    def _validar_tipo_e_gabarito(self) -> "QuestaoAvaliacaoCreate":
        if self.tipo_questao == TipoQuestao.FECHADA and not self.alternativa_correta:
            raise ValueError(
                "Questões do tipo FECHADA exigem o preenchimento de 'alternativa_correta' (A, B, C, D ou E)."
            )
        if self.tipo_questao == TipoQuestao.ABERTA and self.alternativa_correta is not None:
            raise ValueError(
                "Questões do tipo ABERTA não devem possuir 'alternativa_correta'."
            )
        return self


class QuestaoAvaliacaoUpdate(BaseModel):
    """Dados para atualização parcial de uma questão."""

    codigo_questao: Optional[str] = Field(default=None, min_length=1, max_length=30)
    tipo_questao: Optional[TipoQuestao] = None
    alternativa_correta: Optional[str] = Field(default=None, max_length=5)
    valor_questao: Optional[float] = Field(default=None, gt=0.0, le=100.0)
    faixa_dificuldade: Optional[FaixaDificuldadeQuestao] = None
    topico: Optional[str] = Field(default=None, max_length=120)

    @field_validator("alternativa_correta")
    @classmethod
    def _normalizar_alternativa(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpa = v.strip().upper()
        if not limpa:
            return None
        if limpa not in ALTERNATIVAS_VALIDAS_GABARITO:
            raise ValueError(
                f"Alternativa correta inválida ('{v}'). Use uma das opções: A, B, C, D ou E."
            )
        return limpa


class RespostaAvaliacaoCreate(BaseModel):
    """
    Dados para registro ou atualização idempotente da resposta de um estudante a uma questão.
    Permite identificar o estudante por `estudante_id` (UUID) ou `codigo_anonimo`.
    """

    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = Field(default=None, max_length=50)
    alternativa_marcada: Optional[str] = Field(default=None, max_length=10)
    em_branco: Optional[bool] = None
    nota_obtida: Optional[float] = Field(default=None, ge=0.0)
    acertou: Optional[bool] = None

    @field_validator("alternativa_marcada")
    @classmethod
    def _validar_alternativa_marcada(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpa = v.strip().upper()
        if not limpa or limpa in ("-", "EM_BRANCO", "EM BRANCO", "VAZIO"):
            return "BRANCO"
        if limpa not in ALTERNATIVAS_VALIDAS_RESPOSTA:
            raise ValueError(
                f"Alternativa marcada inválida ('{v}'). Use A, B, C, D, E ou BRANCO."
            )
        return limpa

    @model_validator(mode="after")
    def _garantir_identificador_estudante(self) -> "RespostaAvaliacaoCreate":
        if self.estudante_id is None and (
            not self.codigo_anonimo or not self.codigo_anonimo.strip()
        ):
            raise ValueError(
                "Informe 'estudante_id' ou 'codigo_anonimo' para identificar o estudante."
            )
        return self


class QuestaoAvaliacaoResponse(BaseModel):
    """Representação de saída de uma questão."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    avaliacao_id: uuid.UUID
    codigo_questao: str
    tipo_questao: TipoQuestao
    alternativa_correta: Optional[str] = None
    valor_questao: float
    faixa_dificuldade: FaixaDificuldadeQuestao
    topico: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime


class RespostaAvaliacaoResponse(BaseModel):
    """Representação de saída da resposta de um estudante anonimizado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    questao_id: uuid.UUID
    codigo_questao: Optional[str] = None
    estudante_id: uuid.UUID
    codigo_anonimo: Optional[str] = None
    alternativa_marcada: Optional[str] = None
    em_branco: bool
    nota_obtida: float
    acertou: Optional[bool] = None
    criado_em: datetime
    atualizado_em: datetime


class AvaliacaoResponse(BaseModel):
    """Representação de saída de uma avaliação."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    titulo: str
    escola_id: uuid.UUID
    turma_id: uuid.UUID
    turma_nome: Optional[str] = None
    disciplina_id: uuid.UUID
    disciplina_codigo: Optional[str] = None
    disciplina_nome: Optional[str] = None
    usuario_id: uuid.UUID
    periodo_letivo: str
    data_avaliacao: date
    status: StatusAvaliacao
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class AvaliacaoDetalhadaResponse(AvaliacaoResponse):
    """Representação detalhada de uma avaliação com suas questões."""

    questoes: list[QuestaoAvaliacaoResponse] = []

