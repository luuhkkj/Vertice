"""
Modelos ORM para Auditoria de Consultas ao Assistente Inteligente (Fase 7).

Registra todas as solicitações de construção de contexto — autorizadas e negadas —
sem armazenar PII, tokens, senhas ou dados pedagógicos brutos nos metadados de auditoria.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.escolas.models import Escola
    from app.modules.estudantes.models import Estudante
    from app.modules.turmas.models import Turma
    from app.modules.usuarios.models import Usuario


class ResultadoAutorizacaoIA(str, Enum):
    """Resultado da validação de acesso antes da montagem de contexto para IA."""

    AUTORIZADO = "AUTORIZADO"
    NEGADO = "NEGADO"


class TipoContextoAssistente(str, Enum):
    """Níveis estruturados de contexto suportados pelo assistente inteligente."""

    ESCOLA = "ESCOLA"
    TURMA = "TURMA"
    INDIVIDUAL = "INDIVIDUAL"


class AuditoriaConsultaIA(Base):
    """Trilha persistente e auditável de solicitações de contexto ao assistente."""

    __tablename__ = "auditoria_consultas_ia"
    __table_args__ = (
        Index(
            "ix_auditoria_ia_usuario_criado",
            "usuario_id",
            "criado_em",
        ),
        Index(
            "ix_auditoria_ia_resultado_criado",
            "resultado_autorizacao",
            "criado_em",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_auditoria_ia_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    papel_usuario: Mapped[str] = mapped_column(String(30), nullable=False)
    escola_id_solicitada: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_auditoria_ia_escola_id_escolas",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )
    turma_id_solicitada: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_auditoria_ia_turma_id_turmas",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )
    estudante_id_solicitado: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "estudantes.id",
            name="fk_auditoria_ia_estudante_id_estudantes",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )
    tipo_contexto: Mapped[TipoContextoAssistente] = mapped_column(
        SQLEnum(
            TipoContextoAssistente,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
    )
    resultado_autorizacao: Mapped[ResultadoAutorizacaoIA] = mapped_column(
        SQLEnum(
            ResultadoAutorizacaoIA,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
    )
    motivo_decisao: Mapped[str] = mapped_column(String(255), nullable=False)
    filtros_utilizados: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    resumo_fontes_consultadas: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship("Usuario")
    escola: Mapped[Optional["Escola"]] = relationship("Escola")
    turma: Mapped[Optional["Turma"]] = relationship("Turma")
    estudante: Mapped[Optional["Estudante"]] = relationship("Estudante")
