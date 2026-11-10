"""
Schemas Pydantic para o módulo de Usuários.
"""

from datetime import datetime
import re
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.usuarios.models import PapelUsuario

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class UsuarioBase(BaseModel):
    """Atributos comuns de usuário."""

    nome: str = Field(..., min_length=2, max_length=100, description="Nome completo")
    email: str = Field(..., max_length=120, description="E-mail único do usuário")

    @field_validator("email")
    @classmethod
    def validar_e_normalizar_email(cls, v: str) -> str:
        email_limpo = v.strip().lower()
        if not EMAIL_REGEX.match(email_limpo):
            raise ValueError("Formato de e-mail inválido.")
        return email_limpo

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str) -> str:
        nome_limpo = v.strip()
        if len(nome_limpo) < 2:
            raise ValueError("O nome deve ter pelo menos 2 caracteres.")
        return nome_limpo


class UsuarioCreate(UsuarioBase):
    """Dados de entrada para criação de um usuário."""

    senha: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Senha em texto plano (será armazenada como hash)",
    )
    papel: PapelUsuario = Field(
        default=PapelUsuario.PROFESSOR,
        description="Papel do usuário no sistema (administrador, gestor ou professor)",
    )
    escola_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID da escola à qual o usuário (ex: gestor) está vinculado",
    )
    ativo: bool = Field(default=True, description="Define se o usuário está ativo")


class UsuarioUpdate(BaseModel):
    """Dados opcionais para atualização de um usuário."""

    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[str] = Field(None, max_length=120)
    senha: Optional[str] = Field(None, min_length=6, max_length=128)
    papel: Optional[PapelUsuario] = None
    escola_id: Optional[uuid.UUID] = None
    ativo: Optional[bool] = None

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        nome_limpo = v.strip()
        if len(nome_limpo) < 2:
            raise ValueError("O nome deve ter pelo menos 2 caracteres.")
        return nome_limpo

    @field_validator("email")
    @classmethod
    def validar_e_normalizar_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        email_limpo = v.strip().lower()
        if not EMAIL_REGEX.match(email_limpo):
            raise ValueError("Formato de e-mail inválido.")
        return email_limpo


class UsuarioResponse(BaseModel):
    """Dados de saída de um usuário (nunca expõe o hash da senha)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    papel: PapelUsuario
    escola_id: Optional[uuid.UUID] = None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
