"""
Rotas HTTP para gestão e consulta de Turmas.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    require_acesso_pedagogico,
    require_gestor_ou_admin,
    require_qualquer_papel,
)
from app.database.connection import get_db
from app.modules.turmas.models import Turma
from app.modules.turmas.schemas import TurmaCreate, TurmaResponse, TurmaUpdate
from app.modules.turmas.service import TurmaService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "",
    response_model=TurmaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova turma (Administrador ou Gestor)",
)
def criar_turma(
    dados: TurmaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Turma:
    """Cadastra uma nova turma vinculada a uma escola existente, respeitando o escopo do gestor."""
    return TurmaService.criar_turma(db, dados, usuario=current_user)


@router.get(
    "",
    response_model=list[TurmaResponse],
    summary="Listar turmas conforme escopo de acesso do usuário",
)
def listar_turmas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_qualquer_papel),
) -> list[Turma]:
    """
    Lista turmas:
    - Administradores visualizam todas as turmas.
    - Gestores com escola vinculada visualizam as turmas da sua escola.
    - Professores visualizam exclusivamente as turmas às quais estão associados.
    """
    return TurmaService.listar_turmas_por_escopo(
        db, usuario=current_user, skip=skip, limit=limit
    )


@router.get(
    "/{turma_id}",
    response_model=TurmaResponse,
    summary="Obter detalhes de uma turma (Gestor da escola ou Professor vinculado)",
)
def obter_turma(
    turma_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> Turma:
    """
    Retorna os detalhes de uma turma.
    Exclusivo para Gestores (na própria escola) e Professores vinculados (`HTTP 403` para Administrador).
    """
    return TurmaService.obter_turma_autorizada(
        db, turma_id=turma_id, usuario=current_user
    )


@router.patch(
    "/{turma_id}",
    response_model=TurmaResponse,
    summary="Atualizar turma (Administrador ou Gestor)",
)
def atualizar_turma(
    turma_id: uuid.UUID,
    dados: TurmaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Turma:
    """Atualiza dados de uma turma validando unicidade composta e escopo."""
    return TurmaService.atualizar_turma(
        db, turma_id, dados, usuario=current_user
    )
