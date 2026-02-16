from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HabitDefinition

DEFAULT_HABITS = [
    {"key": "wake_early", "title": "Ertalab erta turish", "sort_order": 1},
    {"key": "no_phone_1h", "title": "Telefonsiz 1 soat", "sort_order": 2},
    {"key": "write_plan", "title": "Kundalik reja yozish", "sort_order": 3},
]


def seed_habits_if_empty(db: Session) -> None:
    existing = db.scalar(select(HabitDefinition.id).limit(1))
    if existing:
        return

    for item in DEFAULT_HABITS:
        db.add(HabitDefinition(**item))
    db.commit()


def get_active_habits(db: Session) -> list[HabitDefinition]:
    return list(db.scalars(select(HabitDefinition).where(HabitDefinition.is_active.is_(True)).order_by(HabitDefinition.sort_order)))
