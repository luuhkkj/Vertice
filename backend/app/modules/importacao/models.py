"""
Modelos ORM para o módulo de Importação e Auditoria de Lotes (Fase 3).
Controla o fluxo de importação em duas etapas (validação/prévia e confirmação atômica),
registrando autoria a partir da sessão autenticada e protegendo contra dados pessoais proibidos.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.modules.escolas.models import Escola
    from app.modules.usuarios.models import Usuario


class StatusLoteImportacao(str, Enum):
    """Estados do ciclo de vida de um lote de importação."""

    RECEBIDO = "recebido"
    VALIDANDO = "validando"
    VALIDADO = "validado"
    COM_ERROS = "com_erros"
    CONFIRMADO = "confirmado"
    FALHOU = "falhou"
    DESCARTADO = "descartado"


class TipoImportacao(str, Enum):
    """Tipos de datasets suportados para importação (Fases 3 e 4)."""

    DADOS_ESCOLARES = "DADOS_ESCOLARES"
    AVALIACOES = "AVALIACOES"
    ATIVIDADES = "ATIVIDADES"


class LoteImportacao(Base):
    """
    Entidade de auditoria e controle de lotes de importação em duas etapas.
    O usuário responsável (`usuario_id`) é extraído exclusivamente da sessão JWT autenticada.
    """

    __tablename__ = "lotes_importacao"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "usuarios.id",
            name="fk_lotes_importacao_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "escolas.id",
            name="fk_lotes_importacao_escola_id_escolas",
            ondelete="RESTRICT",
        ),
        index=True,
        nullable=False,
    )
    nome_arquivo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    tipo_importacao: Mapped[TipoImportacao] = mapped_column(
        SQLEnum(
            TipoImportacao,
            native_enum=False,
            length=40,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=TipoImportacao.DADOS_ESCOLARES,
    )
    hash_arquivo: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    status: Mapped[StatusLoteImportacao] = mapped_column(
        SQLEnum(
            StatusLoteImportacao,
            native_enum=False,
            length=30,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        index=True,
        nullable=False,
        default=StatusLoteImportacao.RECEBIDO,
    )
    total_linhas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    registros_validos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    quantidade_erros: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    quantidade_avisos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    registros_novos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    registros_existentes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    registros_inseridos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    registros_atualizados: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    relatorio_validacao: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    dados_previa: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
    )
    enviado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    validado_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmado_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario")
    escola: Mapped["Escola"] = relationship("Escola")

