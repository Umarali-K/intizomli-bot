"""ops hardening: device binding, code expiry, achievements, audit logs

Revision ID: 20260216_0008
Revises: 20260216_0007
Create Date: 2026-02-16 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260216_0008"
down_revision = "20260216_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("device_fingerprint", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("device_bound_at", sa.DateTime(), nullable=True))

    op.add_column("activation_codes", sa.Column("expires_at", sa.DateTime(), nullable=True))

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("code", sa.String(length=64), nullable=False, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("earned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "code", name="uq_user_achievement_user_code"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_tg_user_id", "audit_logs", ["actor_tg_user_id"])
    op.create_index("ix_audit_logs_target_tg_user_id", "audit_logs", ["target_tg_user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target_tg_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_tg_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_table("user_achievements")

    op.drop_column("activation_codes", "expires_at")

    op.drop_column("users", "device_bound_at")
    op.drop_column("users", "device_fingerprint")
