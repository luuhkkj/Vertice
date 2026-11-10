"""
Modelos ORM para o módulo de Participação, Atividades e Entregas (Bloco C — Fase 4).
Mantém separação estrita entre frequência escolar (presença em aula) e participação
em atividades avaliativas/tarefas, e mapeia explicitamente todas as entregas esperadas
dos estudantes vinculados à turma.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
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


class StatusAtividade(str, Enum):
    """Status operacional de uma atividade."""

    ABERTA = "ABERTA"
    ENCERRADA = "ENCERRADA"
    ARQUIVADA = "ARQUIVADA"


class StatusEntregaAtividade(str, Enum):
    """Status previstos de entrega de uma atividade segundo a documentação."""

    ENTREGUE = "ENTREGUE"
    ATRASADO = "ATRASADO"
    PENDENTE = "PENDENTE"
    NAO_ENTREGUE = "NAO_ENTREGUE"


class Atividade(Base):
    """
    Tarefa ou atividade atribuída a uma turma e disciplina, com data limite e nota máxima opcional.
    """

    __tablename__ = "atividades"
    __table_args__ = (
        UniqueConstraint(
            "escola_id",
            "turma_id",
            "disciplina_id",
            "codigo",
            name="uq_atividade_escola_turma_disc_codigo",
        ),
        CheckConstraint(
            "nota_maxima IS NULL OR nota_maxima > 0.0",
            name="ck_atividade_nota_maxima_positiva",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    codigo: Mapped[str] = mapped_column(
        String(60),
        index=True,
        nullable=False,
    )
    titulo: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_atividades_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    turma_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_atividades_turma_id_turmas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    disciplina_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "disciplinas.id",
            name="fk_atividades_disciplina_id_disciplinas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_atividades_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    periodo_letivo: Mapped[str] = mapped_column(
        String(30),
        index=True,
        nullable=False,
    )
    data_limite: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
    )
    nota_maxima: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status: Mapped[StatusAtividade] = mapped_column(
        SQLEnum(
            StatusAtividade,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=StatusAtividade.ABERTA,
        server_default=StatusAtividade.ABERTA.value,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
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
    escola: Mapped["Escola"] = relationship("Escola")
    turma: Mapped["Turma"] = relationship("Turma")
    disciplina: Mapped["Disciplina"] = relationship("Disciplina")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    entregas: Mapped[list["EntregaAtividade"]] = relationship(
        "EntregaAtividade",
        back_populates="atividade",
    )


class EntregaAtividade(Base):
    """
    Registro de entrega esperada e/ou realizada de um estudante anonimizado para uma atividade.
    Notas ausentes permanecem `None` (`NULL`) e nunca são convertidas em zero sem regra explícita.
    """

    __tablename__ = "entregas_atividade"
    __table_args__ = (
        UniqueConstraint(
            "atividade_id",
            "estudante_id",
            name="uq_entrega_atividade_estudante",
        ),
        CheckConstraint(
            "nota IS NULL OR nota >= 0.0",
            name="ck_entrega_atividade_nota_nao_negativa",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    atividade_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "atividades.id",
            name="fk_entregas_atividade_atividade_id_atividades",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    estudante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "estudantes.id",
            name="fk_entregas_atividade_estudante_id_estudantes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    data_entrega: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    nota: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    status_entrega: Mapped[StatusEntregaAtividade] = mapped_column(
        SQLEnum(
            StatusEntregaAtividade,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
        default=StatusEntregaAtividade.PENDENTE,
    )
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
    atividade: Mapped["Atividade"] = relationship(
        "Atividade",
        back_populates="entregas",
    )
    estudante: Mapped["Estudante"] = relationship("Estudante")

