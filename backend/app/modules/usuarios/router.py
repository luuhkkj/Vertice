"""
Rotas HTTP para gestão de Usuários.
Nota de Segurança: Não existe endpoint público para criação de administradores ou usuários.
A criação de usuários exige autenticação com papel de administrador.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_gestor_ou_admin
from app.database.connection import get_db
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.schemas import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.modules.usuarios.service import UsuarioService

router = APIRouter()


@router.post(
    "",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo usuário (Apenas Administrador)",
)
def criar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    _current_admin: Usuario = Depends(require_admin),
) -> Usuario:
    """
    Cria um novo usuário no sistema.
    Restrito exclusivamente a usuários autenticados com papel `administrador`.
    """
    return UsuarioService.criar_usuario(db, dados)


@router.get(
    "",
    response_model=list[UsuarioResponse],
    summary="Listar usuários (Administrador ou Gestor)",
)
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> list[Usuario]:
    """Lista os usuários cadastrados. Permitido para `administrador` e `gestor`."""
    return UsuarioService.listar_usuarios(db, skip=skip, limit=limit)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Obter detalhes de um usuário (Administrador ou Gestor)",
)
def obter_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Usuario:
    """Retorna os detalhes de um usuário pelo ID."""
    return UsuarioService.obter_por_id(db, usuario_id)


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Atualizar dados ou status de um usuário (Apenas Administrador)",
)
def atualizar_usuario(
    usuario_id: uuid.UUID,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    _current_admin: Usuario = Depends(require_admin),
) -> Usuario:
    """Atualiza informações, papel ou status ativo/inativo de um usuário."""
    return UsuarioService.atualizar_usuario(db, usuario_id, dados)

