"""
Repositório de acesso a dados para a entidade LoteImportacao.
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.importacao.models import LoteImportacao


class ImportacaoRepository:
    """Operações de persistência e consulta para lotes de importação."""

    @staticmethod
    def get_by_id(
        db: Session,
        lote_id: uuid.UUID,
        for_update: bool = False,
    ) -> Optional[LoteImportacao]:
        stmt = select(LoteImportacao).where(LoteImportacao.id == lote_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[LoteImportacao]:
        stmt = (
            select(LoteImportacao)
            .where(LoteImportacao.escola_id == escola_id)
            .order_by(LoteImportacao.enviado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_usuario(
        db: Session,
        usuario_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[LoteImportacao]:
        stmt = (
            select(LoteImportacao)
            .where(LoteImportacao.usuario_id == usuario_id)
            .order_by(LoteImportacao.enviado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(db: Session, lote: LoteImportacao) -> LoteImportacao:
        db.add(lote)
        db.commit()
        db.refresh(lote)
        return lote

    @staticmethod
    def update(db: Session, lote: LoteImportacao) -> LoteImportacao:
        db.add(lote)
        db.commit()
        db.refresh(lote)
        return lote

