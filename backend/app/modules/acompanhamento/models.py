"""
Modelos ORM para o módulo de Acompanhamento Pedagógico (Fase 4).
Permite registrar ações pedagógicas individuais (estudante) ou coletivas (turma),
vinculadas à origem (`ESTUDANTES`, `MAPA_ACERTOS`, `PARTICIPACAO`), preservando
integralmente o histórico de edições em `historico_alteracoes`.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.disciplinas.models import Disciplina
    from app.modules.escolas.models import Escola
    from app.modules.estudantes.models import Estudante
    from app.modules.turmas.models import Turma
    from app.modules.usuarios.models import Usuario


class OrigemAcompanhamento(str, Enum):
    """Origens previstas para o registro de acompanhamento pedagógico."""

    ESTUDANTES = "ESTUDANTES"
    MAPA_ACERTOS = "MAPA_ACERTOS"
    PARTICIPACAO = "PARTICIPACAO"


class AcompanhamentoPedagogico(Base):
    """
    Registro de acompanhamento ou intervenção pedagógica individual (`estudante_id`)
    ou coletiva (`turma_id`).
    Exige que pelo menos um entre `estudante_id` e `turma_id` esteja preenchido.
    Atualizações subsequentes registram snapshot anterior em `historico_alteracoes`
    para impedir que o histórico seja apagado silenciosamente.
    """

    __tablename__ = "acompanhamentos_pedagogicos"
    __table_args__ = (
        CheckConstraint(
            "estudante_id IS NOT NULL OR turma_id IS NOT NULL",
            name="ck_acompanhamento_estudante_ou_turma_obrigatorio",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_acompanhamentos_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_acompanhamentos_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    estudante_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "estudantes.id",
            name="fk_acompanhamentos_estudante_id_estudantes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=True,
    )
    turma_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_acompanhamentos_turma_id_turmas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=True,
    )
    disciplina_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "disciplinas.id",
            name="fk_acompanhamentos_disciplina_id_disciplinas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=True,
    )
    origem: Mapped[OrigemAcompanhamento] = mapped_column(
        SQLEnum(
            OrigemAcompanhamento,
            native_enum=False,
            length=30,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
    )
    tipo_acao: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    descricao: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    historico_alteracoes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    data_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
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
    escola: Mapped["Escola"] = relationship("Escola")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    estudante: Mapped[Optional["Estudante"]] = relationship("Estudante")
    turma: Mapped[Optional["Turma"]] = relationship("Turma")
    disciplina: Mapped[Optional["Disciplina"]] = relationship("Disciplina")

