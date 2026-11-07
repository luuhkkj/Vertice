"""
Repositório de acesso a dados para a entidade Escola.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.escolas.models import Escola


class EscolaRepository:
    """Operações de persistência para Escolas."""

    @staticmethod
    def get_by_id(db: Session, escola_id: uuid.UUID) -> Optional[Escola]:
        stmt = select(Escola).where(Escola.id == escola_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_codigo(db: Session, codigo: str) -> Optional[Escola]:
        stmt = select(Escola).where(Escola.codigo == codigo.strip().upper())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Escola]:
        stmt = select(Escola).order_by(Escola.nome).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, escola: Escola) -> Escola:
        db.add(escola)
        db.commit()
        db.refresh(escola)
        return escola

    @staticmethod
    def update(db: Session, escola: Escola) -> Escola:
        db.add(escola)
        db.commit()
        db.refresh(escola)
        return escola

