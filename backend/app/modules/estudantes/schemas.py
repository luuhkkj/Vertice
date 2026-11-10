"""
Schemas Pydantic v2 para consulta de Estudantes, Boletins por Período e Notas por Disciplina.
Nota: Não há schemas de criação/edição manual (a entrada de dados ocorre via importação de datasets).
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.estudantes.models import SituacaoFinalPeriodo


class NotaDisciplinaResponse(BaseModel):
    """Representação do desempenho de um estudante em uma disciplina específica."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    boletim_id: uuid.UUID
    disciplina_id: uuid.UUID
    disciplina_codigo: Optional[str] = None
    disciplina_nome: Optional[str] = None
    nota: Optional[float] = None
    nota_prova: Optional[float] = None
    nota_trabalho: Optional[float] = None
    frequencia_percentual: Optional[float] = None
    faltas: Optional[int] = None
    em_recuperacao: Optional[bool] = None
    criado_em: datetime
    atualizado_em: datetime


class BoletimPeriodoResponse(BaseModel):
    """Representação do boletim / histórico escolar de um estudante em um período letivo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estudante_id: uuid.UUID
    codigo_anonimo: Optional[str] = None
    escola_id: uuid.UUID
    turma_id: uuid.UUID
    turma_nome: Optional[str] = None
    ano_letivo: int
    periodo_letivo: str
    idade: Optional[int] = None
    frequencia_percentual: Optional[float] = None
    faltas: Optional[int] = None
    media_geral: Optional[float] = None
    notas_baixas: Optional[int] = None
    historico_reprovacoes: int
    participacao_recuperacao: Optional[bool] = None
    atrasos: Optional[int] = None
    situacao_final: Optional[SituacaoFinalPeriodo] = None
    notas_disciplina: list[NotaDisciplinaResponse] = []
    criado_em: datetime
    atualizado_em: datetime


class EstudanteResponse(BaseModel):
    """Representação anônima de um estudante."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo_anonimo: str
    escola_id: uuid.UUID
    historico_reprovacoes: int
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime


class EstudanteHistoricoDetalhadoResponse(EstudanteResponse):
    """Representação anônima de um estudante com seus boletins filtrados pelo escopo do usuário."""

    boletins: list[BoletimPeriodoResponse] = []

