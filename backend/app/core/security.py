"""
Módulo de segurança para hashing de senhas e manipulação de tokens JWT.
Preparado para futura autenticação na aplicação Vértice.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Instância de hash de senhas configurada com algoritmos seguros modernos (Argon2 por padrão)
password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    """Gera um hash seguro para a senha informada."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto confere com o hash armazenado."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | Any, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Gera um token JWT com tempo de expiração configurável.
    
    :param subject: Identificador do usuário (ex: ID ou email).
    :param expires_delta: Tempo adicional até a expiração (opcional).
    :return: String codificada do JWT.
    """
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decodifica e valida a assinatura e expiração de um token JWT.
    
    :param token: String do token JWT.
    :return: Dicionário contendo o payload do token decodificado.
    :raises jwt.PyJWTError: Caso o token seja inválido ou esteja expirado.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

