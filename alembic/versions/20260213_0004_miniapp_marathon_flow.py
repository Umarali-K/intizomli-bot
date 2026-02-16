"""miniapp marathon flow tables and user fields

Revision ID: 20260213_0004
Revises: 20260213_0003
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260213_0004"
down_revision: Union[str, None] = "20260213_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    existing_cols = {c["name"] for c in insp.get_columns("users")}

    def add_col(name: str, column) -> None:
        if name not in existing_cols:
            op.add_column("users", column)

    add_col("full_name", sa.Column("full_name", sa.String(length=255), nullable=True))
    add_col("age", sa.Column("age", sa.Integer(), nullable=True))
    add_col("location", sa.Column("location", sa.String(length=255), nullable=True))
    add_col("goal", sa.Column("goal", sa.Text(), nullable=True))
    add_col("pains", sa.Column("pains", sa.Text(), nullable=True))
    add_col("expectations", sa.Column("expectations", sa.Text(), nullable=True))
    add_col("registration_completed", sa.Column("registration_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    add_col("selected_modules_json", sa.Column("selected_modules_json", sa.Text(), nullable=True))
    add_col("habits_json", sa.Column("habits_json", sa.Text(), nullable=True))
    add_col("sports_json", sa.Column("sports_json", sa.Text(), nullable=True))
    add_col("reading_book", sa.Column("reading_book", sa.String(length=255), nullable=True))
    add_col("reading_task", sa.Column("reading_task", sa.String(length=255), nullable=True))
    add_col("reminder_hours_json", sa.Column("reminder_hours_json", sa.String(length=64), nullable=True, server_default="09,14,21"))
    add_col("payment_status", sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="unpaid"))
    add_col("payment_confirmed_at", sa.Column("payment_confirmed_at", sa.DateTime(), nullable=True))
    add_col("cashback_balance_uzs", sa.Column("cashback_balance_uzs", sa.Integer(), nullable=False, server_default="0"))

    tables = set(insp.get_table_names())
    if "daily_module_reports" not in tables:
        op.create_table(
            "daily_module_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("report_date", sa.Date(), nullable=False),
            sa.Column("module", sa.String(length=32), nullable=False),
            sa.Column("item_key", sa.String(length=128), nullable=False),
            sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "report_date", "module", "item_key", name="uq_daily_module_report"),
        )
        op.create_index("ix_daily_module_reports_user_id", "daily_module_reports", ["user_id"], unique=False)
        op.create_index("ix_daily_module_reports_report_date", "daily_module_reports", ["report_date"], unique=False)
        op.create_index("ix_daily_module_reports_module", "daily_module_reports", ["module"], unique=False)
        op.create_index("ix_daily_module_reports_item_key", "daily_module_reports", ["item_key"], unique=False)

    if "challenges" not in tables:
        op.create_table(
            "challenges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("numbers_csv", sa.String(length=32), nullable=False),
            sa.Column("tasks_json", sa.String(length=1024), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_challenges_user_id", "challenges", ["user_id"], unique=False)

    if "cashbacks" not in tables:
        op.create_table(
            "cashbacks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_tg_user_id", sa.BigInteger(), nullable=False),
            sa.Column("from_user_tg_user_id", sa.BigInteger(), nullable=False),
            sa.Column("amount_uzs", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_cashbacks_owner_tg_user_id", "cashbacks", ["owner_tg_user_id"], unique=False)
        op.create_index("ix_cashbacks_from_user_tg_user_id", "cashbacks", ["from_user_tg_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cashbacks_from_user_tg_user_id", table_name="cashbacks")
    op.drop_index("ix_cashbacks_owner_tg_user_id", table_name="cashbacks")
    op.drop_table("cashbacks")

    op.drop_index("ix_challenges_user_id", table_name="challenges")
    op.drop_table("challenges")

    op.drop_index("ix_daily_module_reports_item_key", table_name="daily_module_reports")
    op.drop_index("ix_daily_module_reports_module", table_name="daily_module_reports")
    op.drop_index("ix_daily_module_reports_report_date", table_name="daily_module_reports")
    op.drop_index("ix_daily_module_reports_user_id", table_name="daily_module_reports")
    op.drop_table("daily_module_reports")

    op.drop_column("users", "cashback_balance_uzs")
    op.drop_column("users", "payment_confirmed_at")
    op.drop_column("users", "payment_status")
    op.drop_column("users", "reminder_hours_json")
    op.drop_column("users", "reading_task")
    op.drop_column("users", "reading_book")
    op.drop_column("users", "sports_json")
    op.drop_column("users", "habits_json")
    op.drop_column("users", "selected_modules_json")
    op.drop_column("users", "registration_completed")
    op.drop_column("users", "expectations")
    op.drop_column("users", "pains")
    op.drop_column("users", "goal")
    op.drop_column("users", "location")
    op.drop_column("users", "age")
    op.drop_column("users", "full_name")
