from datetime import date
from typing import Optional

from pydantic import BaseModel


class UserUpsertIn(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


class UserOut(BaseModel):
    tg_user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    status: str
    is_paid: bool
    payment_amount_uzs: int
    marathon_days: int
    marathon_start_date: Optional[date] = None
    onboarding_completed: bool
    rating_points: int
    current_streak: int

    class Config:
        from_attributes = True
