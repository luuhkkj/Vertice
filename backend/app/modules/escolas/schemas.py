"""
Schemas Pydantic para o módulo de Escolas.
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EscolaBase(BaseModel):
    """Atributos comuns de uma unidade escolar."""

    nome: str = Field(..., min_length=2, max_length=150, description="Nome da escola")
    codigo: str = Field(
        ..., min_length=2, max_length=50, description="Código identificador único da escola"
    )

    @field_validator("nome")
    @classmethod
    def limpar_nome(cls, v: str) -> str:
        return v.strip()

    @field_validator("codigo")
    @classmethod
    def limpar_codigo(cls, v: str) -> str:
        return v.strip().upper()


class EscolaCreate(EscolaBase):
    """Dados de entrada para criação de escola."""

    ativo: bool = Field(default=True, description="Define se a escola está ativa")


class EscolaUpdate(BaseModel):
    """Dados opcionais para atualização de escola."""

    nome: Optional[str] = Field(None, min_length=2, max_length=150)
    codigo: Optional[str] = Field(None, min_length=2, max_length=50)
    ativo: Optional[bool] = None

    @field_validator("codigo")
    @classmethod
    def limpar_codigo(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v is not None else None


class EscolaResponse(BaseModel):
    """Dados de saída de uma escola."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    codigo: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime

