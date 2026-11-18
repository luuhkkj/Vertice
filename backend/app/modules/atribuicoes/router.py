"""
Rotas HTTP para gestão pedagógica de Atribuições entre Professores, Turmas e Disciplinas.

Regra estrita de papéis:
- Gestor/Coordenador (`gestor`): cria, lista e remove atribuições exclusivamente da sua escola.
- Professor (`professor`): lista apenas as próprias atribuições (`GET /api/v1/atribuicoes`).
- Administrador (`administrador`): bloqueado com HTTP 403 em todas as rotas de atribuições.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico, require_gestor
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
    summary="Associar professor a turma e disciplina (Apenas Gestor da escola)",
)
def criar_atribuicao(
    dados: AtribuicaoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor),
) -> ProfessorTurma:
    """
    Cria um vínculo pedagógico entre um professor, uma turma e uma disciplina.
    Exclusivo para o Gestor/Coordenador dentro da sua escola vinculada.
    """
    return AtribuicaoService.criar_atribuicao(db, dados, usuario=current_user)


@router.get(
    "",
    response_model=list[AtribuicaoResponse],
    summary="Listar atribuições de professores e turmas (Gestor ou Professor)",
)
def listar_atribuicoes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_acesso_pedagogico),
) -> list[ProfessorTurma]:
    """
    Lista atribuições pedagógicas:
    - Gestores visualizam exclusivamente as atribuições da sua escola vinculada.
    - Professores visualizam exclusivamente suas próprias atribuições.
    - Administradores são bloqueados com HTTP 403.
    """
    return AtribuicaoService.listar_atribuicoes(
        db, usuario=current_user, skip=skip, limit=limit
    )


@router.delete(
    "/{atribuicao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover atribuição (Apenas Gestor da escola)",
)
def remover_atribuicao(
    atribuicao_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_gestor),
) -> Response:
    """Remove o vínculo entre professor, turma e disciplina na escola do gestor."""
    AtribuicaoService.remover_atribuicao(
        db, atribuicao_id, usuario=current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
