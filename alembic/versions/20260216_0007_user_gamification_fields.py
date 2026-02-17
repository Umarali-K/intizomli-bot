"""add gamification and review fields to users

Revision ID: 20260216_0007
Revises: 20260214_0006
Create Date: 2026-02-16 10:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260216_0007"
down_revision = "20260214_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("streak_freeze_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("missed_days_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_report_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("last_weekly_review_sent_at", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("certificate_issued", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("certificate_code", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "certificate_code")
    op.drop_column("users", "certificate_issued")
    op.drop_column("users", "last_weekly_review_sent_at")
    op.drop_column("users", "last_report_date")
    op.drop_column("users", "missed_days_count")
    op.drop_column("users", "streak_freeze_used")
