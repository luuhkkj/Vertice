"""
Rotas HTTP para gestão e consulta de Turmas.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    require_consulta_estrutural,
    require_gestor_ou_admin,
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
    summary="Listar turmas conforme escopo estrutural do usuário",
)
def listar_turmas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_consulta_estrutural),
) -> list[Turma]:
    """
    Lista apenas registros estruturais de turmas:
    - Administradores visualizam registros estruturais de todas as turmas (sem conteúdo pedagógico).
    - Gestores com escola vinculada visualizam as turmas da sua escola.
    - Professores visualizam exclusivamente as turmas às quais estão associados.
    """
    return TurmaService.listar_turmas_por_escopo(
        db, usuario=current_user, skip=skip, limit=limit
    )


@router.get(
    "/{turma_id}",
    response_model=TurmaResponse,
    summary="Obter registro estrutural de uma turma",
)
def obter_turma(
    turma_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_consulta_estrutural),
) -> Turma:
    """
    Retorna apenas os campos cadastrais/estruturais de uma turma (sem estudantes, notas ou avaliações).
    Administrador consulta estruturalmente qualquer turma; Gestor restringe-se à própria escola e
    Professor às turmas com vínculo ativo (`HTTP 403` fora do escopo).
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
