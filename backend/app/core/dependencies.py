"""
Dependências de autenticação, autorização baseada em papéis (RBAC) e escopo de turmas.
"""

from typing import Callable, Optional
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.connection import get_db
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.usuarios.models import PapelUsuario, Usuario

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Recupera e valida o usuário autenticado a partir do token JWT Bearer.
    Rejeita tokens ausentes, inválidos, expirados ou pertencentes a usuários inativos.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: identificador ausente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(str(sub))
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    stmt = select(Usuario).where(Usuario.id == user_id)
    usuario = db.execute(stmt).scalar_one_or_none()

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Autenticação não permitida.",
        )

    return usuario


def require_roles(*allowed_roles: PapelUsuario) -> Callable[[Usuario], Usuario]:
    """
    Fábrica de dependências para exigir que o usuário autenticado possua um dos papéis informados.
    """

    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.papel not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: você não possui permissão para realizar esta ação.",
            )
        return current_user

    return role_checker


# Dependências prontas para uso nas rotas
require_admin = require_roles(PapelUsuario.ADMINISTRADOR)
require_gestor_ou_admin = require_roles(
    PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR
)
require_qualquer_papel = require_roles(
    PapelUsuario.ADMINISTRADOR,
    PapelUsuario.GESTOR,
    PapelUsuario.PROFESSOR,
)


def verificar_vinculo_professor_turma(
    db: Session,
    professor_id: uuid.UUID,
    turma_id: uuid.UUID,
) -> bool:
    """
    Verifica no banco de dados se um professor possui vínculo ativo com uma determinada turma.
    """
    stmt = (
        select(ProfessorTurma.id)
        .where(
            ProfessorTurma.professor_id == professor_id,
            ProfessorTurma.turma_id == turma_id,
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def garantir_acesso_turma(
    db: Session,
    usuario: Usuario,
    turma_id: uuid.UUID,
) -> None:
    """
    Valida se o usuário tem autorização para acessar uma turma específica.
    - Administradores e Gestores possuem acesso irrestrito.
    - Professores só podem acessar turmas às quais estão vinculados.
    Lança HTTPException 403 caso o professor não tenha vínculo.
    """
    if usuario.papel in (PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR):
        return

    if not verificar_vinculo_professor_turma(db, usuario.id, turma_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: professor não possui vínculo com esta turma.",
        )

