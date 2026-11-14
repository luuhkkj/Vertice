"""
Modelos ORM para o módulo de Previsões Preditivas (Fase 7):
- `CredencialIntegracaoPredicao`: credenciais de serviço escopadas para recebimento externo
  de previsões (sem reutilizar tokens de usuários comuns nem armazenar segredos em texto plano).
- `PrevisaoRisco`: armazenamento histórico append-only de previsões de risco educacional
  associadas a estudantes anonimizados, modelos versionados e políticas de classificação.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
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


class TipoPrevisao(str, Enum):
    """Tipos de previsão educacional suportados pelo contrato do Vértice."""

    EVASAO = "EVASAO"
    REPROVACAO = "REPROVACAO"
    RISCO_ACADEMICO = "RISCO_ACADEMICO"


class FaixaRisco(str, Enum):
    """
    Conjunto controlado de faixas de risco recebidas de modelos/políticas explícitas.
    Representam estimativas probabilísticas e nunca um diagnóstico definitivo.
    """

    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class CredencialIntegracaoPredicao(Base):
    """
    Credencial técnica dedicada para pipelines externos de ML enviarem previsões ao Vértice.
    Apenas o prefixo e o hash criptográfico (SHA-256) são armazenados em banco.
    """

    __tablename__ = "credenciais_integracao_predicao"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    prefixo_chave: Mapped[str] = mapped_column(
        String(24),
        index=True,
        nullable=False,
    )
    hash_chave: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )
    escola_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_cred_pred_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=True,
    )
    modelos_permitidos: Mapped[Optional[list[str]]] = mapped_column(
        JSON,
        nullable=True,
    )
    criado_por_usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_cred_pred_criado_por_usuarios",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    expira_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ultimo_uso_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
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

    escola: Mapped[Optional["Escola"]] = relationship("Escola")
    criado_por_usuario: Mapped["Usuario"] = relationship("Usuario")


class PrevisaoRisco(Base):
    """
    Registro histórico imutável (append-only) de uma previsão de risco para um estudante.
    Previsões novas nunca sobrescrevem previsões anteriores; execuções repetidas são
    identificadas e bloqueadas por `assinatura_idempotencia`.
    """

    __tablename__ = "previsoes_risco"
    __table_args__ = (
        UniqueConstraint(
            "assinatura_idempotencia",
            name="uq_previsoes_risco_assinatura_idempotencia",
        ),
        CheckConstraint(
            "pontuacao_risco >= 0.0 AND pontuacao_risco <= 1.0",
            name="ck_previsoes_risco_pontuacao_entre_0_e_1",
        ),
        Index(
            "ix_previsoes_escola_ano_periodo",
            "escola_id",
            "ano_letivo",
            "periodo_letivo",
        ),
        Index(
            "ix_previsoes_estudante_gerado",
            "estudante_id",
            "gerado_em",
        ),
        Index(
            "ix_previsoes_modelo_versao",
            "modelo_nome",
            "modelo_versao",
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
            name="fk_previsoes_estudante_id_estudantes",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_previsoes_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    turma_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "turmas.id",
            name="fk_previsoes_turma_id_turmas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=True,
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
    tipo_previsao: Mapped[TipoPrevisao] = mapped_column(
        SQLEnum(
            TipoPrevisao,
            native_enum=False,
            length=30,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
        default=TipoPrevisao.EVASAO,
    )
    pontuacao_risco: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    faixa_risco: Mapped[FaixaRisco] = mapped_column(
        SQLEnum(
            FaixaRisco,
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
    )
    politica_classificacao_versao: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
    )
    modelo_nome: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    modelo_versao: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )
    gerado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    recebido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    lote_externo_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        index=True,
        nullable=True,
    )
    assinatura_idempotencia: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    metadados_tecnicos: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    credencial_integracao_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "credenciais_integracao_predicao.id",
            name="fk_previsoes_credencial_integracao_id",
            ondelete="SET NULL",
        ),
        index=True,
        nullable=True,
    )
    enviado_por_usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_previsoes_enviado_por_usuario_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    estudante: Mapped["Estudante"] = relationship("Estudante")
    escola: Mapped["Escola"] = relationship("Escola")
    turma: Mapped[Optional["Turma"]] = relationship("Turma")
    credencial_integracao: Mapped[Optional["CredencialIntegracaoPredicao"]] = (
        relationship("CredencialIntegracaoPredicao")
    )
    enviado_por_usuario: Mapped[Optional["Usuario"]] = relationship("Usuario")
