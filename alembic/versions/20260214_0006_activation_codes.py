"""add activation codes

Revision ID: 20260214_0006
Revises: 20260213_0005
Create Date: 2026-02-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260214_0006"
down_revision: Union[str, None] = "20260213_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activation_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("target_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("used_by_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_activation_codes_code", "activation_codes", ["code"], unique=True)
    op.create_index("ix_activation_codes_target_tg_user_id", "activation_codes", ["target_tg_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activation_codes_target_tg_user_id", table_name="activation_codes")
    op.drop_index("ix_activation_codes_code", table_name="activation_codes")
    op.drop_table("activation_codes")
