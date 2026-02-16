from pydantic import BaseModel


class ProfileOut(BaseModel):
    tg_user_id: int
    status: str
    is_paid: bool
    onboarding_completed: bool
    marathon_days: int
    marathon_day_no: int
    remaining_days: int
    rating_points: int
    current_streak: int
    referral_count: int
