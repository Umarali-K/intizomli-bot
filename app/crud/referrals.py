from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Referral


def create_referral(db: Session, referrer_tg_user_id: int, invited_tg_user_id: int) -> None:
    if referrer_tg_user_id == invited_tg_user_id:
        return

    existing = db.scalar(select(Referral).where(Referral.invited_tg_user_id == invited_tg_user_id))
    if existing:
        return

    db.add(
        Referral(
            referrer_tg_user_id=referrer_tg_user_id,
            invited_tg_user_id=invited_tg_user_id,
        )
    )
    db.commit()


def get_referral_count(db: Session, referrer_tg_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Referral)
        .where(Referral.referrer_tg_user_id == referrer_tg_user_id)
    ) or 0
