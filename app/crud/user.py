from datetime import date
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import User


def upsert_user(db: Session, tg_user_id: int, username: Optional[str], first_name: Optional[str]) -> User:
    user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if user:
        user.username = username
        user.first_name = first_name
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    user = User(tg_user_id=tg_user_id, username=username, first_name=first_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_tg_id(db: Session, tg_user_id: int) -> Optional[User]:
    return db.scalar(select(User).where(User.tg_user_id == tg_user_id))


def mark_user_paid(db: Session, tg_user_id: int, payment_amount_uzs: int = 89000) -> Optional[User]:
    user = get_user_by_tg_id(db, tg_user_id)
    if not user:
        return None

    if user.marathon_start_date is None:
        user.marathon_start_date = date.today()
    user.is_paid = True
    user.status = "active"
    user.payment_amount_uzs = payment_amount_uzs
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def complete_user_onboarding(db: Session, tg_user_id: int) -> Optional[User]:
    user = get_user_by_tg_id(db, tg_user_id)
    if not user:
        return None

    user.onboarding_completed = True
    if user.is_paid:
        user.status = "active"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_reportable_users(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(
                or_(User.is_paid.is_(True), User.payment_status == "paid"),
                or_(
                    User.onboarding_completed.is_(True),
                    and_(
                        User.registration_completed.is_(True),
                        User.selected_modules_json.is_not(None),
                    ),
                ),
            )
        )
    )
