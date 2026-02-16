"""add onboarding answers table

Revision ID: 20260213_0003
Revises: 20260213_0002
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260213_0003"
down_revision: Union[str, None] = "20260213_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("item_key", sa.String(length=255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_onboarding_answers_user_id", "onboarding_answers", ["user_id"], unique=False)
    op.create_index("ix_onboarding_answers_module", "onboarding_answers", ["module"], unique=False)
    op.create_index("ix_onboarding_answers_item_key", "onboarding_answers", ["item_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_onboarding_answers_item_key", table_name="onboarding_answers")
    op.drop_index("ix_onboarding_answers_module", table_name="onboarding_answers")
    op.drop_index("ix_onboarding_answers_user_id", table_name="onboarding_answers")
    op.drop_table("onboarding_answers")
