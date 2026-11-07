"""
Repositório de acesso a dados para a entidade Usuario.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.usuarios.models import Usuario


class UsuarioRepository:
    """Operações de banco de dados para usuários."""

    @staticmethod
    def get_by_id(db: Session, usuario_id: uuid.UUID) -> Optional[Usuario]:
        stmt = select(Usuario).where(Usuario.id == usuario_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Usuario]:
        stmt = select(Usuario).where(Usuario.email == email.strip().lower())
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Usuario]:
        stmt = select(Usuario).order_by(Usuario.nome).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, usuario: Usuario) -> Usuario:
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

    @staticmethod
    def update(db: Session, usuario: Usuario) -> Usuario:
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario

