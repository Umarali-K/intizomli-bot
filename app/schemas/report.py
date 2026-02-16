from datetime import date
from typing import Optional

from pydantic import BaseModel


class HabitReportIn(BaseModel):
    tg_user_id: int
    report_date: Optional[date] = None
    checked_keys: list[str]


class DashboardOut(BaseModel):
    day_label: str
    streak: int
    completion_percent: int
    habits: dict[str, bool]
