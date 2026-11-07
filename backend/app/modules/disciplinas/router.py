"""
Rotas HTTP para gestão de Disciplinas.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_gestor_ou_admin, require_qualquer_papel
from app.database.connection import get_db
from app.modules.disciplinas.models import Disciplina
from app.modules.disciplinas.schemas import (
    DisciplinaCreate,
    DisciplinaResponse,
    DisciplinaUpdate,
)
from app.modules.disciplinas.service import DisciplinaService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "",
    response_model=DisciplinaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova disciplina (Administrador ou Gestor)",
)
def criar_disciplina(
    dados: DisciplinaCreate,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Disciplina:
    """Cadastra uma nova disciplina escolar."""
    return DisciplinaService.criar_disciplina(db, dados)


@router.get(
    "",
    response_model=list[DisciplinaResponse],
    summary="Listar disciplinas",
)
def listar_disciplinas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_qualquer_papel),
) -> list[Disciplina]:
    """Lista todas as disciplinas cadastradas."""
    return DisciplinaService.listar_disciplinas(db, skip=skip, limit=limit)


@router.get(
    "/{disciplina_id}",
    response_model=DisciplinaResponse,
    summary="Obter detalhes de uma disciplina",
)
def obter_disciplina(
    disciplina_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_qualquer_papel),
) -> Disciplina:
    """Retorna os detalhes de uma disciplina específica."""
    return DisciplinaService.obter_por_id(db, disciplina_id)


@router.patch(
    "/{disciplina_id}",
    response_model=DisciplinaResponse,
    summary="Atualizar disciplina (Administrador ou Gestor)",
)
def atualizar_disciplina(
    disciplina_id: uuid.UUID,
    dados: DisciplinaUpdate,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Disciplina:
    """Atualiza informações de uma disciplina."""
    return DisciplinaService.atualizar_disciplina(db, disciplina_id, dados)

