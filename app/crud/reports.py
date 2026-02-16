from datetime import date

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from app.models import HabitReport, User
from app.crud.habits import get_active_habits


def save_daily_habit_report(db: Session, user: User, report_date: date, checked_keys: list[str]) -> dict[str, bool]:
    habits = get_active_habits(db)
    active_keys = [h.key for h in habits]
    checked_set = {k for k in checked_keys if k in active_keys}

    db.execute(
        delete(HabitReport).where(
            and_(HabitReport.user_id == user.id, HabitReport.report_date == report_date)
        )
    )

    result: dict[str, bool] = {}
    for key in active_keys:
        is_done = key in checked_set
        db.add(HabitReport(user_id=user.id, report_date=report_date, habit_key=key, is_done=is_done))
        result[key] = is_done

    db.commit()
    return result


def get_habits_state_for_date(db: Session, user: User, report_date: date) -> dict[str, bool]:
    rows = db.execute(
        select(HabitReport.habit_key, HabitReport.is_done).where(
            and_(HabitReport.user_id == user.id, HabitReport.report_date == report_date)
        )
    ).all()
    return {habit_key: is_done for habit_key, is_done in rows}


def get_streak_days(db: Session, user: User) -> int:
    done_dates = db.scalars(
        select(HabitReport.report_date)
        .where(and_(HabitReport.user_id == user.id, HabitReport.is_done.is_(True)))
        .group_by(HabitReport.report_date)
        .order_by(HabitReport.report_date.desc())
    ).all()

    if not done_dates:
        return 0

    streak = 0
    expected = date.today()
    for d in done_dates:
        if d == expected:
            streak += 1
            expected = date.fromordinal(expected.toordinal() - 1)
        elif d < expected:
            break
    return streak


def get_completion_percent(db: Session, user: User, report_date: date) -> int:
    total = db.scalar(
        select(func.count()).select_from(HabitReport).where(
            and_(HabitReport.user_id == user.id, HabitReport.report_date == report_date)
        )
    ) or 0
    if total == 0:
        return 0

    done = db.scalar(
        select(func.count()).select_from(HabitReport).where(
            and_(HabitReport.user_id == user.id, HabitReport.report_date == report_date, HabitReport.is_done.is_(True))
        )
    ) or 0
    return int((done * 100) / total)
