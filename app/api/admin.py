import secrets
import string
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import Integer, and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.models import ActivationCode, AuditLog, DailyModuleReport, PaymentTransaction, User

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _admin_token() -> str:
    # Backward-compatible: use explicit ADMIN_API_TOKEN first, then old ADMIN_CONFIRM_TOKEN if configured.
    return (getattr(settings, "ADMIN_API_TOKEN", "") or getattr(settings, "ADMIN_CONFIRM_TOKEN", "") or "").strip()


def _require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    token = _admin_token()
    if not token:
        raise HTTPException(status_code=503, detail="Admin token configured emas")
    if x_admin_token != token:
        raise HTTPException(status_code=403, detail="Admin token noto'g'ri")


def _gen_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.get("/users")
def admin_users(
    limit: int = 100,
    status: Optional[str] = None,
    q: Optional[str] = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 500))

    query = select(User).order_by(User.created_at.desc()).limit(limit)
    if status:
        query = query.where(User.status == status)

    users = list(db.scalars(query))
    if q:
        q_lower = q.lower().strip()
        users = [
            u for u in users
            if (u.full_name and q_lower in u.full_name.lower())
            or (u.username and q_lower in u.username.lower())
            or q_lower in str(u.tg_user_id)
        ]

    return {
        "count": len(users),
        "items": [
            {
                "tg_user_id": u.tg_user_id,
                "full_name": u.full_name,
                "username": u.username,
                "status": u.status,
                "payment_status": u.payment_status,
                "rating_points": u.rating_points,
                "current_streak": u.current_streak,
                "registration_completed": u.registration_completed,
                "onboarding_completed": u.onboarding_completed,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.get("/payments")
def admin_payments(
    limit: int = 100,
    status: Optional[str] = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 500))

    query = select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc()).limit(limit)
    if status:
        query = query.where(PaymentTransaction.status == status)

    txs = list(db.scalars(query))
    return {
        "count": len(txs),
        "items": [
            {
                "id": t.id,
                "user_id": t.user_id,
                "provider": t.provider,
                "provider_trans_id": t.provider_trans_id,
                "amount_uzs": t.amount_uzs,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in txs
        ],
    }


@router.get("/codes")
def admin_codes(
    limit: int = 200,
    used: Optional[bool] = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 1000))

    query = select(ActivationCode).order_by(ActivationCode.created_at.desc()).limit(limit)
    if used is not None:
        query = query.where(ActivationCode.is_used.is_(used))

    codes = list(db.scalars(query))
    return {
        "count": len(codes),
        "items": [
            {
                "id": c.id,
                "code": c.code,
                "is_used": c.is_used,
                "target_tg_user_id": c.target_tg_user_id,
                "used_by_tg_user_id": c.used_by_tg_user_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "used_at": c.used_at.isoformat() if c.used_at else None,
            }
            for c in codes
        ],
    }


@router.post("/codes/bulk")
def admin_codes_bulk(
    payload: Dict[str, Any],
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    count = int(payload.get("count", 0))
    target_tg_user_id = payload.get("target_tg_user_id")
    if count < 1 or count > 2000:
        raise HTTPException(status_code=400, detail="count 1..2000 bo'lishi kerak")

    target = None
    if target_tg_user_id not in (None, ""):
        target = int(target_tg_user_id)

    created: list[str] = []
    for _ in range(count):
        code = _gen_code()
        while db.scalar(select(ActivationCode).where(ActivationCode.code == code)):
            code = _gen_code()
        db.add(
            ActivationCode(
                code=code,
                target_tg_user_id=target,
                is_used=False,
                expires_at=datetime.utcnow() + timedelta(hours=settings.ACTIVATION_CODE_TTL_HOURS),
            )
        )
        created.append(code)

    db.add(
        AuditLog(
            actor_tg_user_id=None,
            action="admin_bulk_codes",
            target_tg_user_id=target,
            payload_json=f'{{"count": {len(created)}}}',
        )
    )
    db.commit()
    return {
        "ok": True,
        "count": len(created),
        "codes": created,
    }


@router.get("/analytics/overview")
def admin_analytics_overview(
    days: int = 14,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    days = max(1, min(days, 90))
    start = date.today().fromordinal(date.today().toordinal() - (days - 1))

    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    paid_users = db.scalar(select(func.count()).select_from(User).where(User.payment_status == "paid")) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.status == "active")) or 0

    progress_rows = db.execute(
        select(
            DailyModuleReport.module,
            func.count().label("total"),
            func.sum(func.cast(DailyModuleReport.is_done, Integer)).label("done"),
        )
        .where(DailyModuleReport.report_date >= start)
        .group_by(DailyModuleReport.module)
    ).all()

    completion_by_module: Dict[str, int] = {}
    for module, total, done in progress_rows:
        total_i = int(total or 0)
        done_i = int(done or 0)
        completion_by_module[module] = int((done_i * 100) / total_i) if total_i else 0

    today = date.today()
    paid_ids = list(db.scalars(select(User.id).where(User.payment_status == "paid")))
    submitted_ids = list(
        db.scalars(
            select(DailyModuleReport.user_id)
            .where(DailyModuleReport.report_date == today)
            .group_by(DailyModuleReport.user_id)
        )
    )
    missing_count = len(set(paid_ids) - set(submitted_ids))

    return {
        "days": days,
        "totals": {
            "users": int(total_users),
            "paid_users": int(paid_users),
            "active_users": int(active_users),
            "missing_reports_today": int(missing_count),
        },
        "completion_by_module": completion_by_module,
    }


@router.get("/reports/missed")
def admin_reports_missed(
    report_date: Optional[str] = None,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target_date = date.today()
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="report_date format: YYYY-MM-DD") from exc

    paid_users = list(db.scalars(select(User).where(User.payment_status == "paid")))
    submitted_ids = set(
        db.scalars(
            select(DailyModuleReport.user_id)
            .where(DailyModuleReport.report_date == target_date)
            .group_by(DailyModuleReport.user_id)
        )
    )

    missing = [u for u in paid_users if u.id not in submitted_ids]
    return {
        "report_date": target_date.isoformat(),
        "count": len(missing),
        "items": [
            {
                "tg_user_id": u.tg_user_id,
                "full_name": u.full_name,
                "username": u.username,
                "status": u.status,
                "payment_status": u.payment_status,
            }
            for u in missing
        ],
    }


@router.get("/backup/export")
def admin_backup_export(_: None = Depends(_require_admin), db: Session = Depends(get_db)) -> Dict[str, Any]:
    users = list(db.scalars(select(User)))
    codes = list(db.scalars(select(ActivationCode)))
    txs = list(db.scalars(select(PaymentTransaction)))

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "users": len(users),
            "activation_codes": len(codes),
            "payment_transactions": len(txs),
        },
        "users": [
            {
                "tg_user_id": u.tg_user_id,
                "full_name": u.full_name,
                "username": u.username,
                "status": u.status,
                "payment_status": u.payment_status,
                "rating_points": u.rating_points,
                "current_streak": u.current_streak,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "activation_codes": [
            {
                "code": c.code,
                "is_used": c.is_used,
                "target_tg_user_id": c.target_tg_user_id,
                "used_by_tg_user_id": c.used_by_tg_user_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "used_at": c.used_at.isoformat() if c.used_at else None,
            }
            for c in codes
        ],
    }


@router.post("/users/{tg_user_id}/kick")
def admin_user_kick(
    tg_user_id: int,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    before = {
        "status": user.status,
        "is_paid": user.is_paid,
        "payment_status": user.payment_status,
        "onboarding_completed": user.onboarding_completed,
    }
    user.status = "kicked"
    user.is_paid = False
    user.payment_status = "kicked"
    user.onboarding_completed = False
    db.add(user)
    db.add(
        AuditLog(
            actor_tg_user_id=None,
            action="kick_user",
            target_tg_user_id=tg_user_id,
            payload_json=json.dumps({"before": before, "source": "admin_api"}, ensure_ascii=False),
        )
    )
    db.commit()
    return {"ok": True, "tg_user_id": tg_user_id, "status": "kicked"}


@router.post("/users/{tg_user_id}/rollback")
def admin_user_rollback(
    tg_user_id: int,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    log = db.scalar(
        select(AuditLog)
        .where(and_(AuditLog.action == "kick_user", AuditLog.target_tg_user_id == tg_user_id))
        .order_by(AuditLog.created_at.desc())
    )
    if not log or not log.payload_json:
        raise HTTPException(status_code=404, detail="rollback source not found")
    payload = json.loads(log.payload_json)
    before = payload.get("before", {})
    user.status = before.get("status", "unpaid")
    user.is_paid = bool(before.get("is_paid", False))
    user.payment_status = before.get("payment_status", "unpaid")
    user.onboarding_completed = bool(before.get("onboarding_completed", False))
    db.add(user)
    db.add(
        AuditLog(
            actor_tg_user_id=None,
            action="rollback_user",
            target_tg_user_id=tg_user_id,
            payload_json=json.dumps({"source_audit_id": log.id}, ensure_ascii=False),
        )
    )
    db.commit()
    return {"ok": True, "tg_user_id": tg_user_id, "status": user.status}
