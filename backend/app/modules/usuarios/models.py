"""
Modelos ORM para o módulo de Usuários.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.atribuicoes.models import ProfessorTurma


class PapelUsuario(str, Enum):
    """Papéis de acesso permitidos no sistema Vértice."""

    ADMINISTRADOR = "administrador"
    GESTOR = "gestor"
    PROFESSOR = "professor"


class Usuario(Base):
    """Entidade de Usuário do sistema Vértice."""

    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
        nullable=False,
    )
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    papel: Mapped[PapelUsuario] = mapped_column(
        SQLEnum(
            PapelUsuario,
            native_enum=False,
            length=30,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=PapelUsuario.PROFESSOR,
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
    atribuicoes: Mapped[list["ProfessorTurma"]] = relationship(
        "ProfessorTurma",
        back_populates="professor",
    )

