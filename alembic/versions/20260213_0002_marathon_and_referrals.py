"""add marathon fields and referrals

Revision ID: 20260213_0002
Revises: 20260213_0001
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260213_0002"
down_revision: Union[str, None] = "20260213_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("payment_amount_uzs", sa.Integer(), nullable=False, server_default="89000"))
    op.add_column("users", sa.Column("marathon_days", sa.Integer(), nullable=False, server_default="25"))
    op.add_column("users", sa.Column("marathon_start_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("rating_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"))

    op.execute("UPDATE users SET status='unpaid' WHERE status='demo'")

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("invited_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("invited_tg_user_id", name="uq_referrals_invited"),
    )
    op.create_index("ix_referrals_referrer_tg_user_id", "referrals", ["referrer_tg_user_id"], unique=False)
    op.create_index("ix_referrals_invited_tg_user_id", "referrals", ["invited_tg_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_referrals_invited_tg_user_id", table_name="referrals")
    op.drop_index("ix_referrals_referrer_tg_user_id", table_name="referrals")
    op.drop_table("referrals")

    op.drop_column("users", "current_streak")
    op.drop_column("users", "rating_points")
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "marathon_start_date")
    op.drop_column("users", "marathon_days")
    op.drop_column("users", "payment_amount_uzs")
    op.drop_column("users", "is_paid")
