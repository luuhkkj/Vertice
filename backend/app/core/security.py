"""
Módulo de segurança para hashing de senhas e manipulação de tokens JWT.
Utiliza Argon2 via pwdlib e tokens assinados via PyJWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Instância de hash de senhas configurada com Argon2 (recomendado para segurança moderna)
password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    """Gera um hash seguro (Argon2) para a senha informada."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano confere com o hash armazenado."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | Any,
    extra_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Gera um token JWT assinado com tempo de expiração configurável.

    :param subject: Identificador único do usuário (UUID em string).
    :param extra_claims: Claims adicionais (ex: papel do usuário).
    :param expires_delta: Tempo adicional até a expiração (opcional).
    :return: String codificada do JWT.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    if extra_claims:
        for k, v in extra_claims.items():
            if k not in ("sub", "exp", "iat", "type"):
                to_encode[k] = v

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodifica e valida a assinatura e expiração de um token JWT.

    :param token: String do token JWT.
    :return: Dicionário contendo o payload do token decodificado.
    :raises jwt.PyJWTError: Caso o token seja inválido, malformado ou expirado.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
