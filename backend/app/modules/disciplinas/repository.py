"""
Repositório de acesso a dados para a entidade Disciplina.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.disciplinas.models import Disciplina


class DisciplinaRepository:
    """Operações de persistência para Disciplinas."""

    @staticmethod
    def get_by_id(db: Session, disciplina_id: uuid.UUID) -> Optional[Disciplina]:
        stmt = select(Disciplina).where(Disciplina.id == disciplina_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[Disciplina]:
        stmt = select(Disciplina).where(Disciplina.codigo == codigo.strip().upper())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Disciplina]:
        stmt = select(Disciplina).order_by(Disciplina.nome).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, disciplina: Disciplina) -> Disciplina:
        db.add(disciplina)
        db.commit()
        db.refresh(disciplina)
        return disciplina

    @staticmethod
    def update(db: Session, disciplina: Disciplina) -> Disciplina:
        db.add(disciplina)
        db.commit()
        db.refresh(disciplina)
        return disciplina

