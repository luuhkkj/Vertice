"""
Schemas Pydantic para o módulo de Atribuições (ProfessorTurma).
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AtribuicaoCreate(BaseModel):
    """Dados de entrada para associar um professor a uma turma e disciplina."""

    professor_id: uuid.UUID = Field(..., description="ID do usuário com papel de professor")
    turma_id: uuid.UUID = Field(..., description="ID da turma")
    disciplina_id: Optional[uuid.UUID] = Field(
        default=None, description="ID da disciplina lecionada na turma (opcional)"
    )


class AtribuicaoResponse(BaseModel):
    """Dados de saída de uma atribuição entre professor, turma e disciplina."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    professor_id: uuid.UUID
    turma_id: uuid.UUID
    disciplina_id: Optional[uuid.UUID]
    criado_em: datetime

