"""
Camada de serviço para Autenticação e emissão de tokens JWT.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.modules.auth.schemas import TokenResponse, UsuarioAutenticadoResponse
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.repository import UsuarioRepository


class AuthService:
    """Regras de validação de credenciais e geração de tokens."""

    @staticmethod
    def autenticar(db: Session, email: str, senha: str) -> Usuario:
        """
        Valida e-mail, senha e status de ativação do usuário.
        Rejeita credenciais inválidas (401) e usuários inativos (403).
        """
        usuario = UsuarioRepository.get_by_email(db, email)
        if usuario is None or not verify_password(senha, usuario.senha_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-mail ou senha incorretos.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not usuario.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta de usuário inativa. Acesso não autorizado.",
            )

        return usuario

    @staticmethod
    def emitir_token(usuario: Usuario) -> TokenResponse:
        """
        Gera o access_token JWT assinado e monta a resposta padronizada de login.
        """
        access_token = create_access_token(
            subject=str(usuario.id),
            extra_claims={
                "papel": usuario.papel.value,
                "email": usuario.email,
            },
        )
        expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in_seconds,
            usuario=UsuarioAutenticadoResponse.model_validate(usuario),
        )

