"""
Repositório de acesso a dados para a entidade Turma.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.turmas.models import Turma


class TurmaRepository:
    """Operações de persistência e consulta para Turmas."""

    @staticmethod
    def get_by_id(db: Session, turma_id: uuid.UUID) -> Optional[Turma]:
        stmt = select(Turma).where(Turma.id == turma_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_chave_unica(
        db: Session,
        escola_id: uuid.UUID,
        nome: str,
        serie: str,
        turno: str,
        ano_letivo: int,
    ) -> Optional[Turma]:
        stmt = select(Turma).where(
            Turma.escola_id == escola_id,
            Turma.nome == nome.strip(),
            Turma.serie == serie.strip(),
            Turma.turno == turno.strip(),
            Turma.ano_letivo == ano_letivo,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Turma]:
        stmt = (
            select(Turma)
            .order_by(Turma.ano_letivo.desc(), Turma.serie, Turma.nome)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_escola(
        db: Session, escola_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Turma]:
        """Lista exclusivamente as turmas pertencentes a uma escola específica."""
        stmt = (
            select(Turma)
            .where(Turma.escola_id == escola_id)
            .order_by(Turma.ano_letivo.desc(), Turma.serie, Turma.nome)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_professor(
        db: Session, professor_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[Turma]:
        """Lista exclusivamente as turmas às quais um professor possui vínculo."""
        stmt = (
            select(Turma)
            .join(ProfessorTurma, ProfessorTurma.turma_id == Turma.id)
            .where(ProfessorTurma.professor_id == professor_id)
            .distinct()
            .order_by(Turma.ano_letivo.desc(), Turma.serie, Turma.nome)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, turma: Turma) -> Turma:
        db.add(turma)
        db.commit()
        db.refresh(turma)
        return turma

    @staticmethod
    def update(db: Session, turma: Turma) -> Turma:
        db.add(turma)
        db.commit()
        db.refresh(turma)
        return turma
