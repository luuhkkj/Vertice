"""
Repositório de acesso a dados para o módulo de Acompanhamento Pedagógico (Fase 4).
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.acompanhamento.models import (
    AcompanhamentoPedagogico,
    OrigemAcompanhamento,
)


class AcompanhamentoRepository:
    """Consultas e persistência de registros de AcompanhamentoPedagogico."""

    @staticmethod
    def get_by_id(
        db: Session, acompanhamento_id: uuid.UUID
    ) -> Optional[AcompanhamentoPedagogico]:
        stmt = (
            select(AcompanhamentoPedagogico)
            .options(
                selectinload(AcompanhamentoPedagogico.usuario),
                selectinload(AcompanhamentoPedagogico.estudante),
                selectinload(AcompanhamentoPedagogico.turma),
                selectinload(AcompanhamentoPedagogico.disciplina),
            )
            .where(AcompanhamentoPedagogico.id == acompanhamento_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        estudante_id: Optional[uuid.UUID] = None,
        origem: Optional[OrigemAcompanhamento] = None,
        apenas_ativos: bool = True,
    ) -> list[AcompanhamentoPedagogico]:
        stmt = (
            select(AcompanhamentoPedagogico)
            .options(
                selectinload(AcompanhamentoPedagogico.usuario),
                selectinload(AcompanhamentoPedagogico.estudante),
                selectinload(AcompanhamentoPedagogico.turma),
                selectinload(AcompanhamentoPedagogico.disciplina),
            )
            .where(AcompanhamentoPedagogico.escola_id == escola_id)
        )
        if apenas_ativos:
            stmt = stmt.where(AcompanhamentoPedagogico.ativo.is_(True))
        if turma_id is not None:
            stmt = stmt.where(AcompanhamentoPedagogico.turma_id == turma_id)
        if estudante_id is not None:
            stmt = stmt.where(
                AcompanhamentoPedagogico.estudante_id == estudante_id
            )
        if origem is not None:
            stmt = stmt.where(AcompanhamentoPedagogico.origem == origem)
        stmt = stmt.order_by(AcompanhamentoPedagogico.data_registro.desc())
        return list(db.execute(stmt).scalars().all())

