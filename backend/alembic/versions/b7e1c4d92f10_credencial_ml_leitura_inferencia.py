"""credencial_ml_leitura_inferencia

Revision ID: b7e1c4d92f10
Revises: a4d8f2c19b03
Create Date: 2026-11-25 04:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e1c4d92f10"
down_revision: Union[str, None] = "a4d8f2c19b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credenciais_integracao_predicao",
        sa.Column(
            "permite_leitura_inferencia",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("credenciais_integracao_predicao", "permite_leitura_inferencia")
