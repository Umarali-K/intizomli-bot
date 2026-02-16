from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_trans_id", name="uq_payment_provider_trans"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_trans_id: Mapped[str] = mapped_column(String(128), index=True)
    merchant_trans_id: Mapped[str] = mapped_column(String(128), index=True)
    amount_uzs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    click_action: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    click_error: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    click_sign_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
