from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Cashback(Base):
    __tablename__ = "cashbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    from_user_tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount_uzs: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
