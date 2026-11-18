"""
Repositório para persistência e consulta da auditoria técnica administrativa.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.models import AuditoriaOperacaoTecnica


class AdminAuditRepository:
    """Operações de banco de dados para registros técnicos auditáveis."""

    @staticmethod
    def registrar(
        db: Session, registro: AuditoriaOperacaoTecnica
    ) -> AuditoriaOperacaoTecnica:
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    @staticmethod
    def listar(
        db: Session,
        *,
        acao: Optional[str] = None,
        entidade: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditoriaOperacaoTecnica]:
        stmt = select(AuditoriaOperacaoTecnica)
        if acao:
            stmt = stmt.where(AuditoriaOperacaoTecnica.acao == acao.strip().upper())
        if entidade:
            stmt = stmt.where(
                AuditoriaOperacaoTecnica.entidade == entidade.strip().lower()
            )
        stmt = (
            stmt.order_by(AuditoriaOperacaoTecnica.criado_em.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())
