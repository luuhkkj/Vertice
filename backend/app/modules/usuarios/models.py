"""
Modelos ORM para o módulo de Usuários.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.atribuicoes.models import ProfessorTurma
    from app.modules.escolas.models import Escola


class PapelUsuario(str, Enum):
    """
    Papéis de acesso definidos na especificação da Fase 2.
    Nota Arquitetural: A documentação inicial cita 'COORDENADOR' no dicionário de dados,
    enquanto a especificação da Fase 2 define 'administrador', 'gestor' e 'professor'.
    Não é assumida equivalência implícita entre 'gestor' e 'coordenador'; qualquer inclusão
    do papel 'coordenador' depende de decisão formal do responsável pelo projeto.
    """

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
    escola_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("escolas.id", name="fk_usuarios_escola_id_escolas", ondelete="RESTRICT"),
        index=True,
        nullable=True,
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
    escola: Mapped[Optional["Escola"]] = relationship("Escola")
    atribuicoes: Mapped[list["ProfessorTurma"]] = relationship(
        "ProfessorTurma",
        back_populates="professor",
    )
