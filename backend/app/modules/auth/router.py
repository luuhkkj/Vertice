"""
Rotas HTTP para Autenticação (login, me, logout, refresh).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.modules.auth.schemas import LoginRequest, LogoutResponse, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.schemas import UsuarioResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuário e obter token JWT",
)
def login(
    credenciais: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Autentica um usuário ativo com e-mail e senha e retorna um `access_token` JWT
    com tempo de expiração e os dados básicos do usuário autenticado.
    """
    usuario = AuthService.autenticar(db, credenciais.email, credenciais.senha)
    return AuthService.emitir_token(usuario)


@router.get(
    "/me",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter dados do usuário autenticado",
)
def obter_usuario_atual(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """
    Retorna os dados cadastrais do usuário autenticado a partir do token JWT Bearer.
    """
    return current_user


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Encerrar sessão do usuário (Stateless JWT)",
)
def logout(
    _current_user: Usuario = Depends(get_current_user),
) -> LogoutResponse:
    """
    Documenta o encerramento de sessão para autenticação baseada em access token stateless.
    IMPORTANTE: Como a autenticação atual utiliza exclusivamente access tokens JWT stateless,
    o logout exige o descarte imediato do token pelo cliente (frontend) e não representa
    revogação em lista de bloqueio no servidor até a introdução de refresh tokens persistidos.
    """
    return LogoutResponse(
        message="Sessão encerrada pelo cliente.",
        detail=(
            "A autenticação atual opera de forma stateless com access token JWT. "
            "O cliente deve descartar o token armazenado localmente. "
            "Esta operação não efetua revogação do access token no servidor."
        ),
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Renovação de token (Prevista para etapa posterior)",
)
def refresh_token() -> None:
    """
    Endpoint reservado para renovação de tokens.
    Documentado para etapa posterior quando houver persistência, rotação e revogação
    segura de refresh tokens em banco de dados.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Estratégia de refresh token com armazenamento e revogação em banco "
            "será implementada em etapa posterior. Realize nova autenticação em /api/v1/auth/login."
        ),
    )

