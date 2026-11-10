"""
Schemas Pydantic para o módulo de Turmas.
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TurmaBase(BaseModel):
    """Atributos comuns de uma turma."""

    nome: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Identificação da turma (ex: Turma A)",
    )
    serie: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Série escolar (ex: 1ª Série)",
    )
    turno: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Turno (ex: Matutino, Vespertino)",
    )
    ano_letivo: int = Field(
        ..., ge=2000, le=2100, description="Ano letivo da turma"
    )
    escola_id: uuid.UUID = Field(
        ..., description="ID da escola à qual a turma pertence"
    )

    @field_validator("nome", "serie", "turno")
    @classmethod
    def limpar_texto(cls, v: str) -> str:
        limpo = v.strip()
        if not limpo:
            raise ValueError("O campo não pode ser vazio.")
        return limpo


class TurmaCreate(TurmaBase):
    """Dados de entrada para criação de turma."""

    ativo: bool = Field(default=True, description="Define se a turma está ativa")


class TurmaUpdate(BaseModel):
    """Dados opcionais para atualização de turma."""

    nome: Optional[str] = Field(None, min_length=1, max_length=50)
    serie: Optional[str] = Field(None, min_length=1, max_length=30)
    turno: Optional[str] = Field(None, min_length=1, max_length=30)
    ano_letivo: Optional[int] = Field(None, ge=2000, le=2100)
    ativo: Optional[bool] = None

    @field_validator("nome", "serie", "turno")
    @classmethod
    def limpar_texto(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpo = v.strip()
        if not limpo:
            raise ValueError("O campo não pode ser vazio.")
        return limpo


class TurmaResponse(BaseModel):
    """Dados de saída de uma turma."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    serie: str
    turno: str
    ano_letivo: int
    escola_id: uuid.UUID
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
