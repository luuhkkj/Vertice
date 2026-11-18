"""alinhamento_auditoria_operacoes_tecnicas

Revision ID: a4d8f2c19b03
Revises: fe9cc2998c62
Create Date: 2026-11-18 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d8f2c19b03"
down_revision: Union[str, None] = "fe9cc2998c62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auditoria_operacoes_tecnicas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_ator_id", sa.Uuid(), nullable=True),
        sa.Column("papel_ator", sa.String(length=30), nullable=False),
        sa.Column("acao", sa.String(length=80), nullable=False),
        sa.Column("entidade", sa.String(length=60), nullable=False),
        sa.Column("entidade_id", sa.Uuid(), nullable=True),
        sa.Column("detalhes", sa.JSON(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usuario_ator_id"],
            ["usuarios.id"],
            name="fk_auditoria_tec_usuario_ator_id_usuarios",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auditoria_tec_acao_criado",
        "auditoria_operacoes_tecnicas",
        ["acao", "criado_em"],
        unique=False,
    )
    op.create_index(
        "ix_auditoria_tec_entidade_criado",
        "auditoria_operacoes_tecnicas",
        ["entidade", "criado_em"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auditoria_operacoes_tecnicas_acao"),
        "auditoria_operacoes_tecnicas",
        ["acao"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auditoria_operacoes_tecnicas_criado_em"),
        "auditoria_operacoes_tecnicas",
        ["criado_em"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auditoria_operacoes_tecnicas_entidade"),
        "auditoria_operacoes_tecnicas",
        ["entidade"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auditoria_operacoes_tecnicas_entidade_id"),
        "auditoria_operacoes_tecnicas",
        ["entidade_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auditoria_operacoes_tecnicas_usuario_ator_id"),
        "auditoria_operacoes_tecnicas",
        ["usuario_ator_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_auditoria_operacoes_tecnicas_usuario_ator_id"),
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        op.f("ix_auditoria_operacoes_tecnicas_entidade_id"),
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        op.f("ix_auditoria_operacoes_tecnicas_entidade"),
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        op.f("ix_auditoria_operacoes_tecnicas_criado_em"),
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        op.f("ix_auditoria_operacoes_tecnicas_acao"),
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        "ix_auditoria_tec_entidade_criado",
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_index(
        "ix_auditoria_tec_acao_criado",
        table_name="auditoria_operacoes_tecnicas",
    )
    op.drop_table("auditoria_operacoes_tecnicas")
