"""
Rotas HTTP para gestão de Usuários.
Nota de Segurança: Não existe endpoint público para criação de administradores ou usuários.
A criação de usuários exige autenticação com papel de administrador.
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_gestor_ou_admin
from app.database.connection import get_db
from app.modules.usuarios.models import PapelUsuario, Usuario
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
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    papel: Optional[PapelUsuario] = Query(
        default=None,
        description="Filtra opcionalmente por papel (administrador, gestor ou professor).",
    ),
    apenas_ativos: bool = Query(
        default=False,
        description="Quando verdadeiro, retorna apenas usuários ativos.",
    ),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor_ou_admin),
) -> list[Usuario]:
    """
    Lista usuários respeitando o escopo: `administrador` vê todos;
    `gestor` vê os usuários vinculados à sua escola (e professores multi-escola sem vínculo fixo).
    """
    return UsuarioService.listar_usuarios(
        db,
        skip=skip,
        limit=limit,
        current_user=current_user,
        papel=papel,
        apenas_ativos=apenas_ativos,
    )


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Obter detalhes de um usuário (Administrador ou Gestor)",
)
def obter_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Usuario:
    """Retorna os detalhes de um usuário pelo ID respeitando o escopo do solicitante."""
    return UsuarioService.obter_por_id(db, usuario_id, current_user=current_user)


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

