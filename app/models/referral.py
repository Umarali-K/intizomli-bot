from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("invited_tg_user_id", name="uq_referrals_invited"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    referrer_tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    invited_tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
