"""
Repositório de acesso a dados para a entidade Usuario.
"""

from typing import Optional
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.usuarios.models import PapelUsuario, Usuario


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
    def list_filtered(
        db: Session,
        *,
        escola_id_escopo: Optional[uuid.UUID] = None,
        incluir_professores_sem_escola: bool = False,
        papel: Optional[PapelUsuario] = None,
        apenas_ativos: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Usuario]:
        """Lista usuários com filtros opcionais de papel, status ativo e escopo escolar."""
        stmt = select(Usuario)
        if escola_id_escopo is not None:
            if incluir_professores_sem_escola:
                stmt = stmt.where(
                    or_(
                        Usuario.escola_id == escola_id_escopo,
                        (
                            (Usuario.papel == PapelUsuario.PROFESSOR)
                            & (Usuario.escola_id.is_(None))
                        ),
                    )
                )
            else:
                stmt = stmt.where(Usuario.escola_id == escola_id_escopo)
        if papel is not None:
            stmt = stmt.where(Usuario.papel == papel)
        if apenas_ativos:
            stmt = stmt.where(Usuario.ativo.is_(True))
        stmt = stmt.order_by(Usuario.nome).offset(skip).limit(limit)
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

