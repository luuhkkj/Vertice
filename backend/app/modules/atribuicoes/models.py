"""
Modelos ORM para o módulo de Atribuições (ProfessorTurma).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.disciplinas.models import Disciplina
    from app.modules.turmas.models import Turma
    from app.modules.usuarios.models import Usuario


class ProfessorTurma(Base):
    """
    Entidade de associação entre professores, turmas e disciplinas.
    Define o escopo de acesso de cada professor às turmas correspondentes.
    """

    __tablename__ = "professor_turmas"
    __table_args__ = (
        UniqueConstraint(
            "professor_id",
            "turma_id",
            "disciplina_id",
            name="uq_professor_turma_disciplina",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    professor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    turma_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("turmas.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    disciplina_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("disciplinas.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relacionamentos
    professor: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="atribuicoes",
    )
    turma: Mapped["Turma"] = relationship(
        "Turma",
        back_populates="atribuicoes",
    )
    disciplina: Mapped[Optional["Disciplina"]] = relationship(
        "Disciplina",
        back_populates="atribuicoes",
    )

