"""
Rotas HTTP para gestão de Escolas.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_gestor_ou_admin, require_qualquer_papel
from app.database.connection import get_db
from app.modules.escolas.models import Escola
from app.modules.escolas.schemas import (
    EscolaCreate,
    EscolaResponse,
    EscolaUpdate,
)
from app.modules.escolas.service import EscolaService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "",
    response_model=EscolaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova escola (Administrador ou Gestor)",
)
def criar_escola(
    dados: EscolaCreate,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Escola:
    """Cria uma nova escola no sistema."""
    return EscolaService.criar_escola(db, dados)


@router.get(
    "",
    response_model=list[EscolaResponse],
    summary="Listar escolas",
)
def listar_escolas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_qualquer_papel),
) -> list[Escola]:
    """Lista as escolas acessíveis ao usuário autenticado."""
    return EscolaService.listar_escolas(db, skip=skip, limit=limit, usuario=current_user)


@router.get(
    "/{escola_id}",
    response_model=EscolaResponse,
    summary="Obter detalhes de uma escola",
)
def obter_escola(
    escola_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_qualquer_papel),
) -> Escola:
    """Retorna os dados de uma escola acessível ao usuário autenticado."""
    return EscolaService.obter_por_id(db, escola_id, usuario=current_user)


@router.patch(
    "/{escola_id}",
    response_model=EscolaResponse,
    summary="Atualizar escola (Administrador ou Gestor da unidade)",
)
def atualizar_escola(
    escola_id: uuid.UUID,
    dados: EscolaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Escola:
    """Atualiza dados cadastrais ou status de uma escola respeitando escopo do gestor."""
    return EscolaService.atualizar_escola(
        db, escola_id, dados, usuario=current_user
    )
