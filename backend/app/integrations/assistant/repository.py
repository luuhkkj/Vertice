"""
Repositório de persistência e consulta da trilha de auditoria do Assistente IA (Fase 7).
"""

from typing import Optional
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.integrations.assistant.models import (
    AuditoriaConsultaIA,
    ResultadoAutorizacaoIA,
)


class AssistantAuditRepository:
    """Persistência e leitura de eventos de auditoria do contexto IA."""

    @staticmethod
    def registrar(
        db: Session,
        registro: AuditoriaConsultaIA,
    ) -> AuditoriaConsultaIA:
        db.add(registro)
        db.commit()
        db.refresh(registro)
        return registro

    @staticmethod
    def listar(
        db: Session,
        escola_id: Optional[uuid.UUID] = None,
        usuario_id: Optional[uuid.UUID] = None,
        resultado_autorizacao: Optional[ResultadoAutorizacaoIA] = None,
        request_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditoriaConsultaIA]:
        stmt = select(AuditoriaConsultaIA)
        if escola_id is not None:
            stmt = stmt.where(AuditoriaConsultaIA.escola_id_solicitada == escola_id)
        if usuario_id is not None:
            stmt = stmt.where(AuditoriaConsultaIA.usuario_id == usuario_id)
        if resultado_autorizacao is not None:
            stmt = stmt.where(
                AuditoriaConsultaIA.resultado_autorizacao == resultado_autorizacao
            )
        if request_id is not None:
            stmt = stmt.where(AuditoriaConsultaIA.request_id == request_id)
        if conversation_id is not None:
            stmt = stmt.where(AuditoriaConsultaIA.conversation_id == conversation_id)
        stmt = (
            stmt.order_by(desc(AuditoriaConsultaIA.criado_em))
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())
