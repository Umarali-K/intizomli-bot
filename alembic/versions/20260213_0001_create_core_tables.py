"""create core tables

Revision ID: 20260213_0001
Revises: 
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260213_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="demo"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_tg_user_id", "users", ["tg_user_id"], unique=True)

    op.create_table(
        "habit_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_habit_definitions_key", "habit_definitions", ["key"], unique=True)

    op.create_table(
        "habit_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("habit_key", sa.String(length=64), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "report_date", "habit_key", name="uq_habit_report_per_day"),
    )
    op.create_index("ix_habit_reports_user_id", "habit_reports", ["user_id"], unique=False)
    op.create_index("ix_habit_reports_report_date", "habit_reports", ["report_date"], unique=False)
    op.create_index("ix_habit_reports_habit_key", "habit_reports", ["habit_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_habit_reports_habit_key", table_name="habit_reports")
    op.drop_index("ix_habit_reports_report_date", table_name="habit_reports")
    op.drop_index("ix_habit_reports_user_id", table_name="habit_reports")
    op.drop_table("habit_reports")

    op.drop_index("ix_habit_definitions_key", table_name="habit_definitions")
    op.drop_table("habit_definitions")

    op.drop_index("ix_users_tg_user_id", table_name="users")
    op.drop_table("users")
