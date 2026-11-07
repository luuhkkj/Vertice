"""
Rotas HTTP para gestão de Atribuições entre Professores, Turmas e Disciplinas.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_gestor_ou_admin, require_qualquer_papel
from app.database.connection import get_db
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.atribuicoes.schemas import AtribuicaoCreate, AtribuicaoResponse
from app.modules.atribuicoes.service import AtribuicaoService
from app.modules.usuarios.models import Usuario

router = APIRouter()


@router.post(
    "",
    response_model=AtribuicaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Associar professor a turma e disciplina (Administrador ou Gestor)",
)
def criar_atribuicao(
    dados: AtribuicaoCreate,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> ProfessorTurma:
    """
    Cria um vínculo entre um professor, uma turma e uma disciplina.
    Impede duplicidades e valida se o usuário informado possui o papel `professor`.
    """
    return AtribuicaoService.criar_atribuicao(db, dados)


@router.get(
    "",
    response_model=list[AtribuicaoResponse],
    summary="Listar atribuições de professores e turmas",
)
def listar_atribuicoes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_qualquer_papel),
) -> list[ProfessorTurma]:
    """
    Lista atribuições:
    - Administradores e Gestores visualizam todas as atribuições.
    - Professores visualizam exclusivamente suas próprias atribuições.
    """
    return AtribuicaoService.listar_atribuicoes(
        db, usuario=current_user, skip=skip, limit=limit
    )


@router.delete(
    "/{atribuicao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover atribuição (Administrador ou Gestor)",
)
def remover_atribuicao(
    atribuicao_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: Usuario = Depends(require_gestor_ou_admin),
) -> Response:
    """Remove o vínculo entre professor, turma e disciplina."""
    AtribuicaoService.remover_atribuicao(db, atribuicao_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

