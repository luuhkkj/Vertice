"""
Modelos ORM para o módulo de Estudantes e Histórico Escolar Longitudinal (Fase 3).
Respeita rigorosamente a privacidade e anonimização (LGPD / RN01), sem armazenar
nomes completos, CPF, endereço, telefone, e-mail pessoal ou dados biométricos.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    Float,
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
    from app.modules.disciplinas.models import Disciplina
    from app.modules.escolas.models import Escola
    from app.modules.turmas.models import Turma


class SituacaoFinalPeriodo(str, Enum):
    """
    Situação consolidada de um estudante ao final do período letivo.
    Permanece NULL enquanto o período estiver em andamento (prevenção de Data Leakage).
    """

    APROVADO = "Aprovado"
    REPROVADO = "Reprovado"
    EVADIDO = "Evadido"


class Estudante(Base):
    """
    Cadastro base e anonimizado de um estudante vinculado a uma unidade escolar.
    Não contém informações pessoais identificáveis (PII).
    """

    __tablename__ = "estudantes"
    __table_args__ = (
        UniqueConstraint(
            "escola_id",
            "codigo_anonimo",
            name="uq_estudante_escola_codigo_anonimo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    codigo_anonimo: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_estudantes_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    historico_reprovacoes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
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
    boletins: Mapped[list["BoletimPeriodo"]] = relationship(
        "BoletimPeriodo",
        back_populates="estudante",
        cascade="all, delete-orphan",
    )


class BoletimPeriodo(Base):
    """
    Histórico escolar longitudinal / boletim consolidado de um estudante
    em um contexto escolar (escola, turma, ano letivo e período letivo).
    Não sobrescreve períodos anteriores.
    """

    __tablename__ = "boletins_periodo"
    __table_args__ = (
        UniqueConstraint(
            "estudante_id",
            "escola_id",
            "turma_id",
            "ano_letivo",
            "periodo_letivo",
            name="uq_boletim_estudante_escola_turma_ano_periodo",
        ),
        CheckConstraint(
            "frequencia_percentual IS NULL OR (frequencia_percentual >= 0.0 AND frequencia_percentual <= 100.0)",
            name="ck_boletim_frequencia_valida",
        ),
        CheckConstraint(
            "media_geral IS NULL OR (media_geral >= 0.0 AND media_geral <= 10.0)",
            name="ck_boletim_media_geral_valida",
        ),
        CheckConstraint(
            "faltas IS NULL OR faltas >= 0",
            name="ck_boletim_faltas_nao_negativas",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    estudante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "estudantes.id",
            name="fk_boletins_estudante_id_estudantes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_boletins_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    turma_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_boletins_turma_id_turmas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    ano_letivo: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
    )
    periodo_letivo: Mapped[str] = mapped_column(
        String(30),
        index=True,
        nullable=False,
    )
    idade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frequencia_percentual: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    faltas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    media_geral: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    notas_baixas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    historico_reprovacoes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    participacao_recuperacao: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    atrasos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    situacao_final: Mapped[Optional[SituacaoFinalPeriodo]] = mapped_column(
        SQLEnum(
            SituacaoFinalPeriodo,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
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
    estudante: Mapped["Estudante"] = relationship(
        "Estudante",
        back_populates="boletins",
    )
    escola: Mapped["Escola"] = relationship("Escola")
    turma: Mapped["Turma"] = relationship("Turma")
    notas_disciplina: Mapped[list["NotaDisciplina"]] = relationship(
        "NotaDisciplina",
        back_populates="boletim",
        cascade="all, delete-orphan",
    )


class NotaDisciplina(Base):
    """
    Desempenho granular do estudante em uma disciplina específica dentro de um período letivo.
    Garante separação por disciplina sem misturar notas de matérias diferentes e sem
    redundância de `professor_id` (o escopo de acesso é validado via `ProfessorTurma`).
    """

    __tablename__ = "notas_disciplina"
    __table_args__ = (
        UniqueConstraint(
            "boletim_id",
            "disciplina_id",
            name="uq_nota_disciplina_boletim_disciplina",
        ),
        CheckConstraint(
            "nota IS NULL OR (nota >= 0.0 AND nota <= 10.0)",
            name="ck_nota_disciplina_nota_valida",
        ),
        CheckConstraint(
            "nota_prova IS NULL OR (nota_prova >= 0.0 AND nota_prova <= 10.0)",
            name="ck_nota_disciplina_nota_prova_valida",
        ),
        CheckConstraint(
            "nota_trabalho IS NULL OR (nota_trabalho >= 0.0 AND nota_trabalho <= 10.0)",
            name="ck_nota_disciplina_nota_trabalho_valida",
        ),
        CheckConstraint(
            "frequencia_percentual IS NULL OR (frequencia_percentual >= 0.0 AND frequencia_percentual <= 100.0)",
            name="ck_nota_disciplina_frequencia_valida",
        ),
        CheckConstraint(
            "faltas IS NULL OR faltas >= 0",
            name="ck_nota_disciplina_faltas_nao_negativas",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    boletim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "boletins_periodo.id",
            name="fk_notas_disciplina_boletim_id_boletins",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )
    disciplina_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "disciplinas.id",
            name="fk_notas_disciplina_disciplina_id_disciplinas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    nota: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nota_prova: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nota_trabalho: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    frequencia_percentual: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    faltas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    em_recuperacao: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
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
    boletim: Mapped["BoletimPeriodo"] = relationship(
        "BoletimPeriodo",
        back_populates="notas_disciplina",
    )
    disciplina: Mapped["Disciplina"] = relationship("Disciplina")

