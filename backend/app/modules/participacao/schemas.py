"""
Schemas Pydantic v2 para o módulo de Participação, Atividades e Entregas (Bloco C — Fase 4).
"""

from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.participacao.models import StatusAtividade, StatusEntregaAtividade


class AtividadeCreate(BaseModel):
    """Dados para criação de uma nova atividade avaliativa ou tarefa."""

    codigo: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=60,
        description="Código identificador da atividade na turma/disciplina (ex: ATIV-MAT-01). Se omitido, será gerado automaticamente.",
    )
    titulo: str = Field(..., min_length=2, max_length=150)
    turma_id: uuid.UUID
    disciplina_id: uuid.UUID
    periodo_letivo: str = Field(..., min_length=1, max_length=30)
    data_limite: date
    nota_maxima: Optional[float] = Field(default=10.0, gt=0.0, le=100.0)
    status: StatusAtividade = StatusAtividade.ABERTA
    gerar_entregas_esperadas: bool = Field(
        default=False,
        description="Se True, gera imediatamente os registros de entrega esperados para os estudantes já vinculados à turma.",
    )


class AtividadeUpdate(BaseModel):
    """Dados para atualização parcial de uma atividade."""

    titulo: Optional[str] = Field(default=None, min_length=2, max_length=150)
    periodo_letivo: Optional[str] = Field(default=None, min_length=1, max_length=30)
    data_limite: Optional[date] = None
    nota_maxima: Optional[float] = Field(default=None, gt=0.0, le=100.0)
    status: Optional[StatusAtividade] = None
    ativo: Optional[bool] = None


class EntregaAtividadeUpsert(BaseModel):
    """
    Dados para registrar ou atualizar a entrega de um estudante em uma atividade.
    Nota ausente permanece `None` (nunca é convertida em zero sem regra explícita).
    """

    estudante_id: Optional[uuid.UUID] = None
    codigo_anonimo: Optional[str] = Field(default=None, max_length=50)
    data_entrega: Optional[date] = None
    nota: Optional[float] = Field(default=None, ge=0.0)
    status_entrega: Optional[StatusEntregaAtividade] = None

    @model_validator(mode="after")
    def _garantir_identificador_estudante(self) -> "EntregaAtividadeUpsert":
        if self.estudante_id is None and (
            not self.codigo_anonimo or not self.codigo_anonimo.strip()
        ):
            raise ValueError(
                "Informe 'estudante_id' ou 'codigo_anonimo' para identificar o estudante."
            )
        return self


class EntregaAtividadeUpdate(BaseModel):
    """Dados para atualização parcial de um registro de entrega pelo ID."""

    data_entrega: Optional[date] = None
    nota: Optional[float] = Field(default=None, ge=0.0)
    status_entrega: Optional[StatusEntregaAtividade] = None


class EntregaAtividadeResponse(BaseModel):
    """Representação de saída do registro de entrega de uma atividade."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    atividade_id: uuid.UUID
    estudante_id: uuid.UUID
    codigo_anonimo: Optional[str] = None
    data_entrega: Optional[date] = None
    data_limite: Optional[date] = None
    nota: Optional[float] = None
    nota_maxima: Optional[float] = None
    status_entrega: StatusEntregaAtividade
    em_atraso: bool = False
    dias_atraso: int = 0
    criado_em: datetime
    atualizado_em: datetime


class AtividadeResponse(BaseModel):
    """Representação de saída de uma atividade."""

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
    data_limite: date
    nota_maxima: Optional[float] = None
    status: StatusAtividade
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class GeracaoEntregasEsperadasResponse(BaseModel):
    """Resumo da geração idempotente de entregas esperadas para uma atividade."""

    atividade_id: uuid.UUID
    turma_id: uuid.UUID
    total_estudantes_elegiveis: int
    entregas_criadas: int
    entregas_ja_existentes: int
    entregas_atualizadas_para_nao_entregue: int
    mensagem: str

