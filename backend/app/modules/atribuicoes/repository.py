"""
Repositório de acesso a dados para a entidade ProfessorTurma.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma


class AtribuicaoRepository:
    """Operações de banco de dados para atribuições de professores a turmas."""

    @staticmethod
    def get_by_id(db: Session, atribuicao_id: uuid.UUID) -> Optional[ProfessorTurma]:
        stmt = select(ProfessorTurma).where(ProfessorTurma.id == atribuicao_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_composicao(
        db: Session,
        professor_id: uuid.UUID,
        turma_id: uuid.UUID,
        disciplina_id: Optional[uuid.UUID],
    ) -> Optional[ProfessorTurma]:
        if disciplina_id is None:
            stmt = select(ProfessorTurma).where(
                ProfessorTurma.professor_id == professor_id,
                ProfessorTurma.turma_id == turma_id,
                ProfessorTurma.disciplina_id.is_(None),
            )
        else:
            stmt = select(ProfessorTurma).where(
                ProfessorTurma.professor_id == professor_id,
                ProfessorTurma.turma_id == turma_id,
                ProfessorTurma.disciplina_id == disciplina_id,
            )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(
        db: Session, skip: int = 0, limit: int = 100
    ) -> list[ProfessorTurma]:
        stmt = (
            select(ProfessorTurma)
            .order_by(ProfessorTurma.criado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_professor(
        db: Session, professor_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[ProfessorTurma]:
        stmt = (
            select(ProfessorTurma)
            .where(ProfessorTurma.professor_id == professor_id)
            .order_by(ProfessorTurma.criado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, atribuicao: ProfessorTurma) -> ProfessorTurma:
        db.add(atribuicao)
        db.commit()
        db.refresh(atribuicao)
        return atribuicao

    @staticmethod
    def delete(db: Session, atribuicao: ProfessorTurma) -> None:
        db.delete(atribuicao)
        db.commit()

