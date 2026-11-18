"""
Modelo ORM para trilha de auditoria de operações técnicas e administrativas sensíveis.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.usuarios.models import Usuario


class AuditoriaOperacaoTecnica(Base):
    """Registro persistente de ações administrativas/técnicas sensíveis sem PII ou segredos."""

    __tablename__ = "auditoria_operacoes_tecnicas"
    __table_args__ = (
        Index(
            "ix_auditoria_tec_acao_criado",
            "acao",
            "criado_em",
        ),
        Index(
            "ix_auditoria_tec_entidade_criado",
            "entidade",
            "criado_em",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    usuario_ator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_auditoria_tec_usuario_ator_id_usuarios",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )
    papel_ator: Mapped[str] = mapped_column(String(30), nullable=False)
    acao: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entidade: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    entidade_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    detalhes: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    usuario_ator: Mapped[Optional["Usuario"]] = relationship("Usuario")
