"""
Schemas Pydantic para o módulo de Autenticação (Auth).
"""

from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.usuarios.models import PapelUsuario


class LoginRequest(BaseModel):
    """Credenciais de entrada para autenticação de usuário."""

    email: str = Field(..., description="E-mail institucional do usuário")
    senha: str = Field(..., min_length=1, description="Senha do usuário")

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class UsuarioAutenticadoResponse(BaseModel):
    """Dados básicos do usuário retornados junto com o token de acesso."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    papel: PapelUsuario
    escola_id: Optional[uuid.UUID] = None
    ativo: bool


class TokenResponse(BaseModel):
    """Resposta do endpoint de login contendo o token JWT e dados básicos do usuário."""

    access_token: str = Field(..., description="Token JWT assinado")
    token_type: str = Field(
        default="bearer", description="Tipo do token de autorização"
    )
    expires_in: int = Field(
        ..., description="Tempo de expiração do token em segundos"
    )
    usuario: UsuarioAutenticadoResponse = Field(
        ..., description="Dados básicos do usuário autenticado"
    )


class LogoutResponse(BaseModel):
    """Resposta documentando o encerramento de sessão."""

    message: str
    detail: str
