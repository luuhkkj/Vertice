"""
Schemas Pydantic para o módulo de Disciplinas.
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DisciplinaBase(BaseModel):
    """Atributos comuns de uma disciplina."""

    nome: str = Field(..., min_length=2, max_length=100, description="Nome da disciplina (ex: Matemática)")
    codigo: str = Field(..., min_length=2, max_length=50, description="Código único da disciplina (ex: MAT)")

    @field_validator("nome")
    @classmethod
    def limpar_nome(cls, v: str) -> str:
        return v.strip()

    @field_validator("codigo")
    @classmethod
    def limpar_codigo(cls, v: str) -> str:
        return v.strip().upper()


class DisciplinaCreate(DisciplinaBase):
    """Dados de entrada para criação de disciplina."""

    ativo: bool = Field(default=True, description="Define se a disciplina está ativa")


class DisciplinaUpdate(BaseModel):
    """Dados opcionais para atualização de disciplina."""

    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    codigo: Optional[str] = Field(None, min_length=2, max_length=50)
    ativo: Optional[bool] = None

    @field_validator("codigo")
    @classmethod
    def limpar_codigo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v is not None else None


class DisciplinaResponse(BaseModel):
    """Dados de saída de uma disciplina."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    codigo: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

