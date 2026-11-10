"""
Modelos ORM para o módulo de Avaliações, Questões e Respostas (Bloco B — Fase 4).
Sustenta o Mapa de Acertos e indicadores de avaliações, garantindo:
- Isolamento por escola, turma e disciplina.
- Diferenciação explícita entre questões FECHADAS (com gabarito A..E) e ABERTAS.
- Representação explícita de respostas em branco (`em_branco=True` / `alternativa_marcada="BRANCO"`)
  sem confundi-las com ausência de estudante.
- Proteção histórica (`ondelete="RESTRICT"`).
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


class StatusAvaliacao(str, Enum):
    """Status operacional de uma avaliação."""

    RASCUNHO = "RASCUNHO"
    PUBLICADA = "PUBLICADA"
    ENCERRADA = "ENCERRADA"
    ARQUIVADA = "ARQUIVADA"


class TipoQuestao(str, Enum):
    """Tipos previstos de questão avaliativa."""

    FECHADA = "FECHADA"
    ABERTA = "ABERTA"


class FaixaDificuldadeQuestao(str, Enum):
    """Faixa de dificuldade ou desempenho da questão segundo a documentação."""

    FACIL = "Fácil"
    ADEQUADA = "Adequada"
    ATENCAO = "Atenção"
    DIFICIL = "Difícil"


ALTERNATIVAS_VALIDAS_GABARITO = {"A", "B", "C", "D", "E"}
ALTERNATIVAS_VALIDAS_RESPOSTA = {"A", "B", "C", "D", "E", "BRANCO"}


class Avaliacao(Base):
    """
    Instrumento avaliativo aplicado a uma turma e disciplina em um período letivo.
    """

    __tablename__ = "avaliacoes"
    __table_args__ = (
        UniqueConstraint(
            "escola_id",
            "turma_id",
            "disciplina_id",
            "codigo",
            name="uq_avaliacao_escola_turma_disc_codigo",
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
            name="fk_avaliacoes_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    turma_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_avaliacoes_turma_id_turmas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    disciplina_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "disciplinas.id",
            name="fk_avaliacoes_disciplina_id_disciplinas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_avaliacoes_usuario_id_usuarios",
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
    data_avaliacao: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
    )
    status: Mapped[StatusAvaliacao] = mapped_column(
        SQLEnum(
            StatusAvaliacao,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=StatusAvaliacao.PUBLICADA,
        server_default=StatusAvaliacao.PUBLICADA.value,
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
    questoes: Mapped[list["QuestaoAvaliacao"]] = relationship(
        "QuestaoAvaliacao",
        back_populates="avaliacao",
        order_by="QuestaoAvaliacao.codigo_questao",
    )


class QuestaoAvaliacao(Base):
    """
    Questão pertencente a uma avaliação, suportando itens FECHADOS (com gabarito A-E)
    e ABERTOS (avaliados por nota atribuída até `valor_questao`).
    """

    __tablename__ = "questoes_avaliacao"
    __table_args__ = (
        UniqueConstraint(
            "avaliacao_id",
            "codigo_questao",
            name="uq_questao_avaliacao_codigo",
        ),
        CheckConstraint(
            "valor_questao > 0.0",
            name="ck_questao_avaliacao_valor_positivo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    avaliacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "avaliacoes.id",
            name="fk_questoes_avaliacao_avaliacao_id_avaliacoes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    codigo_questao: Mapped[str] = mapped_column(
        String(30),
        index=True,
        nullable=False,
    )
    tipo_questao: Mapped[TipoQuestao] = mapped_column(
        SQLEnum(
            TipoQuestao,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    alternativa_correta: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
    )
    valor_questao: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    faixa_dificuldade: Mapped[Optional[FaixaDificuldadeQuestao]] = mapped_column(
        SQLEnum(
            FaixaDificuldadeQuestao,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
        default=FaixaDificuldadeQuestao.ADEQUADA,
    )
    topico: Mapped[Optional[str]] = mapped_column(
        String(120),
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
    avaliacao: Mapped["Avaliacao"] = relationship(
        "Avaliacao",
        back_populates="questoes",
    )
    respostas: Mapped[list["RespostaAvaliacao"]] = relationship(
        "RespostaAvaliacao",
        back_populates="questao",
    )


class RespostaAvaliacao(Base):
    """
    Resposta de um estudante anonimizado a uma questão de avaliação.
    Impede duplicidades por `(questao_id, estudante_id)` e distingue claramente
    respostas em branco (`em_branco=True`) de erros ou acertos.
    """

    __tablename__ = "respostas_avaliacao"
    __table_args__ = (
        UniqueConstraint(
            "questao_id",
            "estudante_id",
            name="uq_resposta_avaliacao_questao_estudante",
        ),
        CheckConstraint(
            "nota_obtida >= 0.0",
            name="ck_resposta_avaliacao_nota_nao_negativa",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    questao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "questoes_avaliacao.id",
            name="fk_respostas_avaliacao_questao_id_questoes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    estudante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "estudantes.id",
            name="fk_respostas_avaliacao_estudante_id_estudantes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    alternativa_marcada: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    em_branco: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    nota_obtida: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )
    acertou: Mapped[Optional[bool]] = mapped_column(
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
    questao: Mapped["QuestaoAvaliacao"] = relationship(
        "QuestaoAvaliacao",
        back_populates="respostas",
    )
    estudante: Mapped["Estudante"] = relationship("Estudante")
