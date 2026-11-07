"""
Modelos ORM para o módulo de Turmas.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.atribuicoes.models import ProfessorTurma
    from app.modules.escolas.models import Escola


class Turma(Base):
    """Entidade que representa uma turma escolar de um ano letivo."""

    __tablename__ = "turmas"
    __table_args__ = (
        UniqueConstraint(
            "escola_id",
            "nome",
            "serie",
            "turno",
            "ano_letivo",
            name="uq_turma_escola_nome_serie_turno_ano",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    serie: Mapped[str] = mapped_column(String(30), nullable=False)
    turno: Mapped[str] = mapped_column(String(30), nullable=False)
    ano_letivo: Mapped[int] = mapped_column(Integer, nullable=False)
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("escolas.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relacionamentos
    escola: Mapped["Escola"] = relationship("Escola", back_populates="turmas")
    atribuicoes: Mapped[list["ProfessorTurma"]] = relationship(
        "ProfessorTurma",
        back_populates="turma",
    )

