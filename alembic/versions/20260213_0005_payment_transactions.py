"""add payment transactions table

Revision ID: 20260213_0005
Revises: 20260213_0004
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260213_0005"
down_revision: Union[str, None] = "20260213_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_trans_id", sa.String(length=128), nullable=False),
        sa.Column("merchant_trans_id", sa.String(length=128), nullable=False),
        sa.Column("amount_uzs", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("click_action", sa.Integer(), nullable=True),
        sa.Column("click_error", sa.Integer(), nullable=True),
        sa.Column("click_sign_time", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_trans_id", name="uq_payment_provider_trans"),
    )
    op.create_index("ix_payment_transactions_user_id", "payment_transactions", ["user_id"], unique=False)
    op.create_index("ix_payment_transactions_provider", "payment_transactions", ["provider"], unique=False)
    op.create_index("ix_payment_transactions_provider_trans_id", "payment_transactions", ["provider_trans_id"], unique=False)
    op.create_index("ix_payment_transactions_merchant_trans_id", "payment_transactions", ["merchant_trans_id"], unique=False)
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_merchant_trans_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_provider_trans_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_provider", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_user_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
