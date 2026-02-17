from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="unpaid")
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_amount_uzs: Mapped[int] = mapped_column(Integer, default=89000)
    marathon_days: Mapped[int] = mapped_column(Integer, default=25)
    marathon_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pains: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expectations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registration_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_modules_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    habits_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sports_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reading_book: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reading_task: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reminder_hours_json: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    payment_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    streak_freeze_used: Mapped[bool] = mapped_column(Boolean, default=False)
    missed_days_count: Mapped[int] = mapped_column(Integer, default=0)
    last_report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_weekly_review_sent_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    certificate_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    device_bound_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cashback_balance_uzs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
