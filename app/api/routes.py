import json
import os
import hashlib
import base64
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import Integer, and_, delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.crud import get_referral_count, upsert_user
from app.models import ActivationCode, Challenge, DailyModuleReport, PaymentTransaction, User

router = APIRouter()

PAYMENT_AMOUNT_UZS = 89000
ADMIN_CONFIRM_TOKEN = os.getenv("ADMIN_CONFIRM_TOKEN", "")
CLICK_CHECKOUT_BASE_URL = os.getenv("CLICK_CHECKOUT_BASE_URL", "").strip()
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "").strip()
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "").strip()
CLICK_SECRET_TOKEN = os.getenv("CLICK_SECRET_TOKEN", "").strip()
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "").strip()
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "").strip()
PAYME_CHECKOUT_BASE_URL = os.getenv("PAYME_CHECKOUT_BASE_URL", "https://checkout.paycom.uz").strip().rstrip("/")
PAYME_KEY = os.getenv("PAYME_KEY", "").strip()
ADMIN_CONTACT_USERNAME = os.getenv("ADMIN_CONTACT_USERNAME", "").strip().lstrip("@")
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "manual_code").strip().lower()

HABIT_TEMPLATES = [
    "Ertalab erta turish",
    "Telefonsiz 1 soat",
    "Kundalik reja yozish",
    "Shikoyatsiz kun",
    "Duo / tafakkur",
    "Uyqudan oldin kun tahlili",
]
SPORT_TEMPLATES = ["Yugurish", "Piyoda yurish", "Otjimaniya", "Turnik", "Press"]
CHALLENGE_POOL = {
    1: "Sovuq dush",
    2: "3 km piyoda yurish",
    3: "Shikoyatsiz kun",
    4: "100 otjimaniya",
    5: "30 daqiqa mutolaa",
    6: "Shakarni cheklash",
    7: "Ijtimoiy tarmoqlarsiz 4 soat",
    8: "10 000 qadam",
    9: "Erta uyqu",
    10: "Tongda yugurish",
}
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_UZ = {
    "mon": "Dushanba",
    "tue": "Seshanba",
    "wed": "Chorshanba",
    "thu": "Payshanba",
    "fri": "Juma",
    "sat": "Shanba",
    "sun": "Yakshanba",
}


def _dumps(items: List[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def _loads(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return []


def _loads_any_json(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_days(raw_days: Any) -> List[str]:
    if not isinstance(raw_days, list):
        return ["daily"]
    days: List[str] = []
    for item in raw_days:
        val = str(item).strip().lower()
        if val == "daily":
            return ["daily"]
        if val in WEEKDAY_KEYS and val not in days:
            days.append(val)
    return days or ["daily"]


def _today_day_key() -> str:
    return WEEKDAY_KEYS[date.today().weekday()]


def _is_today_selected(days: List[str]) -> bool:
    if "daily" in days:
        return True
    return _today_day_key() in days


def _get_user_or_404(db: Session, tg_user_id: int) -> User:
    user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _marathon_day(user: User) -> int:
    if not user.marathon_start_date:
        return 0
    return max(0, (date.today() - user.marathon_start_date).days + 1)


def _is_setup_completed(user: User) -> bool:
    return bool(user.selected_modules_json)


def _is_active(user: User) -> bool:
    return user.registration_completed and _is_setup_completed(user) and user.payment_status == "paid"


def _level_from_points(points: int) -> Dict[str, Any]:
    if points >= 900:
        return {"name": "Legend", "tier": 5}
    if points >= 600:
        return {"name": "Titan", "tier": 4}
    if points >= 350:
        return {"name": "Oltin", "tier": 3}
    if points >= 150:
        return {"name": "Kumush", "tier": 2}
    return {"name": "Bronza", "tier": 1}


def _weighted_daily_score(done_by_module: Dict[str, int], total_by_module: Dict[str, int]) -> int:
    weights = {"habits": 40, "sports": 35, "reading": 25}
    score = 0.0
    for module, weight in weights.items():
        total = int(total_by_module.get(module, 0))
        done = int(done_by_module.get(module, 0))
        ratio = (done / total) if total else 0.0
        score += ratio * weight
    return int(round(score))


def _issue_certificate_if_ready(user: User) -> None:
    day_no = _marathon_day(user)
    if user.certificate_issued:
        return
    if day_no < user.marathon_days:
        return
    code = f"CERT-{user.tg_user_id}-{day_no}"
    user.certificate_issued = True
    user.certificate_code = code


def _challenge_tasks(numbers: List[int]) -> List[str]:
    tasks: List[str] = []
    for number in numbers:
        if number in CHALLENGE_POOL:
            tasks.append(CHALLENGE_POOL[number])
        else:
            tasks.append(CHALLENGE_POOL[(number % 10) + 1])
    return tasks


def _activate_user(user: User) -> None:
    user.payment_status = "paid"
    user.is_paid = True
    user.payment_confirmed_at = datetime.utcnow()
    user.status = "active"
    if not user.marathon_start_date:
        user.marathon_start_date = date.today()


def _build_click_payment_url(user: User) -> Optional[str]:
    if not (CLICK_CHECKOUT_BASE_URL and CLICK_SERVICE_ID and CLICK_MERCHANT_ID):
        return None

    params = {
        "merchant_id": CLICK_MERCHANT_ID,
        "service_id": CLICK_SERVICE_ID,
        "amount": PAYMENT_AMOUNT_UZS,
        "transaction_param": user.tg_user_id,
    }
    return f"{CLICK_CHECKOUT_BASE_URL}?{urlencode(params)}"


def _build_payme_payment_url(user: User) -> Optional[str]:
    if not PAYME_MERCHANT_ID:
        return None
    amount_tiyin = PAYMENT_AMOUNT_UZS * 100
    return (
        f"{PAYME_CHECKOUT_BASE_URL}/{PAYME_MERCHANT_ID}"
        f"?amount={amount_tiyin}&account[tg_user_id]={user.tg_user_id}"
    )


def _payme_ok(result: Dict[str, Any], req_id: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def _payme_err(code: int, message: str, req_id: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}


def _payme_auth_valid(request: Request) -> bool:
    if not PAYME_KEY:
        return True

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        token = auth.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            if decoded == f"Paycom:{PAYME_KEY}":
                return True
        except Exception:
            return False

    xauth = request.headers.get("x-auth", "")
    if xauth.startswith("Paycom ") and xauth.replace("Paycom ", "", 1).strip() == PAYME_KEY:
        return True

    return False


def _click_prepare_response(click_trans_id: str, merchant_trans_id: str, merchant_prepare_id: int, error: int, error_note: str) -> Dict[str, Any]:
    return {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": merchant_prepare_id,
        "error": error,
        "error_note": error_note,
    }


def _click_complete_response(click_trans_id: str, merchant_trans_id: str, merchant_confirm_id: int, error: int, error_note: str) -> Dict[str, Any]:
    return {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": merchant_confirm_id,
        "error": error,
        "error_note": error_note,
    }


def _click_sign_prepare(click_trans_id: str, merchant_trans_id: str, amount: str, action: str, sign_time: str) -> str:
    raw = f"{click_trans_id}{CLICK_SERVICE_ID}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _click_sign_complete(
    click_trans_id: str,
    merchant_trans_id: str,
    merchant_prepare_id: str,
    amount: str,
    action: str,
    sign_time: str,
) -> str:
    raw = f"{click_trans_id}{CLICK_SERVICE_ID}{CLICK_SECRET_KEY}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def _parse_click_payload(request: Request) -> Dict[str, str]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        data = await request.json()
        return {str(k): str(v) for k, v in (data or {}).items()}

    body = (await request.body()).decode("utf-8")
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def _daily_items_for_user(db: Session, user: User) -> Dict[str, List[str]]:
    modules = _loads(user.selected_modules_json)
    result: Dict[str, List[str]] = {}

    if "habits" in modules:
        habits_raw = _loads_any_json(user.habits_json, [])
        habits_items: List[str] = []
        if habits_raw and isinstance(habits_raw[0], str):
            habits_items = [str(x) for x in habits_raw]
        else:
            for item in habits_raw:
                name = str((item or {}).get("name", "")).strip()
                days = _normalize_days((item or {}).get("days", ["daily"]))
                if name and _is_today_selected(days):
                    habits_items.append(name)
        result["habits"] = habits_items
    if "sports" in modules:
        sports_raw = _loads_any_json(user.sports_json, [])
        sports_items: List[str] = []
        if sports_raw and isinstance(sports_raw[0], str):
            sports_items = [str(x) for x in sports_raw]
        else:
            for item in sports_raw:
                name = str((item or {}).get("name", "")).strip()
                days = _normalize_days((item or {}).get("days", ["daily"]))
                target = (item or {}).get("target_count")
                if not name or not _is_today_selected(days):
                    continue
                if isinstance(target, int) and target > 0:
                    sports_items.append(f"{name} ({target} marta)")
                else:
                    sports_items.append(name)
        result["sports"] = sports_items
    if "reading" in modules:
        result["reading"] = [f"{user.reading_book or 'Intizom kuchi'} — {user.reading_task or '30 bet'}"]

    day_no = _marathon_day(user)
    if "challenge" in modules and day_no >= 5:
        challenge = db.scalar(
            select(Challenge)
            .where(Challenge.user_id == user.id)
            .where(Challenge.status == "active")
            .order_by(Challenge.id.desc())
        )
        if challenge and challenge.start_date <= date.today() <= challenge.end_date:
            try:
                result["challenge"] = json.loads(challenge.tasks_json)
            except Exception:
                result["challenge"] = []

    return {k: v for k, v in result.items() if v}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/app/bootstrap")
def app_bootstrap(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    tg_user_id = int(payload.get("tg_user_id", 0))
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="tg_user_id required")

    user = upsert_user(db, tg_user_id, payload.get("username"), payload.get("first_name"))
    referral_count = get_referral_count(db, tg_user_id)

    return {
        "tg_user_id": user.tg_user_id,
        "templates": {
            "habits": HABIT_TEMPLATES,
            "sports": SPORT_TEMPLATES,
            "modules": ["habits", "sports", "reading"],
            "default_book": "Intizom kuchi",
            "weekdays": [{"key": key, "label": WEEKDAY_UZ[key]} for key in WEEKDAY_KEYS],
        },
        "payment": {
            "mode": PAYMENT_MODE,
            "admin_username": ADMIN_CONTACT_USERNAME,
            "admin_url": f"https://t.me/{ADMIN_CONTACT_USERNAME}" if ADMIN_CONTACT_USERNAME else None,
        },
        "state": {
            "registration_completed": user.registration_completed,
            "setup_completed": _is_setup_completed(user),
            "payment_status": user.payment_status,
            "is_active": _is_active(user),
            "marathon_day": _marathon_day(user),
            "marathon_days": user.marathon_days,
            "referral_count": referral_count,
        },
    }


@router.post("/v1/app/register")
def app_register(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))

    full_name = str(payload.get("full_name") or "").strip()
    location = str(payload.get("location") or "").strip()
    goal = str(payload.get("goal") or "").strip()
    pains = str(payload.get("pains") or "").strip()
    expectations = str(payload.get("expectations") or "").strip()

    if len(full_name) < 3:
        raise HTTPException(status_code=400, detail="Iltimos, 'Ism familiya' bo'limini to'g'ri to'ldiring.")
    if len(location) < 2:
        raise HTTPException(status_code=400, detail="Iltimos, 'Qayerdanligi' bo'limini to'g'ri to'ldiring.")
    if len(goal) < 5:
        raise HTTPException(status_code=400, detail="Iltimos, 'Maqsad' bo'limini to'g'ri to'ldiring.")
    if len(pains) < 5:
        raise HTTPException(status_code=400, detail="Iltimos, 'Og'riqlar va muammolar' bo'limini to'g'ri to'ldiring.")
    if len(expectations) < 5:
        raise HTTPException(status_code=400, detail="Iltimos, 'Kutilmalar' bo'limini to'g'ri to'ldiring.")

    raw_age = payload.get("age")
    try:
        age = int(str(raw_age).strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Iltimos, 'Yosh' bo'limini raqamda to'g'ri kiriting.") from exc
    if age < 9 or age > 80:
        raise HTTPException(status_code=400, detail="Iltimos, 'Yosh' bo'limini to'g'ri to'ldiring (9..80).")

    user.full_name = full_name
    user.age = age
    user.location = location
    user.goal = goal
    user.pains = pains
    user.expectations = expectations
    user.registration_completed = True
    db.add(user)
    db.commit()

    return {"ok": True, "registration_completed": True}


@router.post("/v1/app/setup")
def app_setup(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))
    if not user.registration_completed:
        raise HTTPException(status_code=400, detail="complete registration first")

    allowed_modules = {"habits", "sports", "reading"}
    modules = [str(x).strip() for x in payload.get("modules", []) if str(x).strip() in allowed_modules]
    modules = list(dict.fromkeys(modules))
    if not modules:
        raise HTTPException(status_code=400, detail="Kamida bitta modul tanlang.")

    setup = payload.get("setup") if isinstance(payload.get("setup"), dict) else {}
    raw_habits = setup.get("habits", payload.get("habits", []))
    raw_sports = setup.get("sports", payload.get("sports", []))
    raw_reading = setup.get("reading", {})

    habits_plan: List[Dict[str, Any]] = []
    if "habits" in modules:
        if not isinstance(raw_habits, list):
            raise HTTPException(status_code=400, detail="Odatlar ro'yxati noto'g'ri.")
        for item in raw_habits:
            if isinstance(item, str):
                name = item.strip()
                days = ["daily"]
            else:
                name = str((item or {}).get("name", "")).strip()
                days = _normalize_days((item or {}).get("days", ["daily"]))
            if not name:
                continue
            habits_plan.append({"name": name, "days": days})
        if len(habits_plan) < 3 or len(habits_plan) > 6:
            raise HTTPException(status_code=400, detail="Odatlar soni 3 tadan 6 tagacha bo'lishi kerak.")

    sports_plan: List[Dict[str, Any]] = []
    if "sports" in modules:
        if not isinstance(raw_sports, list):
            raise HTTPException(status_code=400, detail="Sport ro'yxati noto'g'ri.")
        for item in raw_sports:
            if isinstance(item, str):
                name = item.strip()
                days = ["daily"]
                target = None
            else:
                name = str((item or {}).get("name", "")).strip()
                days = _normalize_days((item or {}).get("days", ["daily"]))
                target_raw = (item or {}).get("target_count")
                try:
                    target = int(target_raw) if target_raw not in (None, "", 0) else None
                except Exception:
                    target = None
            if not name:
                continue
            sports_plan.append({"name": name, "days": days, "target_count": target})
        if len(sports_plan) < 1 or len(sports_plan) > 3:
            raise HTTPException(status_code=400, detail="Sportlar soni 1 tadan 3 tagacha bo'lishi kerak.")

    reading_payload = raw_reading if isinstance(raw_reading, dict) else {}
    reading_book = str(
        reading_payload.get("book")
        or payload.get("reading_book")
        or "Intizom kuchi"
    ).strip()
    reading_pages_raw = reading_payload.get("pages_per_day", payload.get("reading_pages_per_day", 30))
    try:
        reading_pages = int(reading_pages_raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Mutolaa sahifa miqdorini raqamda kiriting.") from exc
    if "reading" in modules and (reading_pages < 1 or reading_pages > 300):
        raise HTTPException(status_code=400, detail="Mutolaa sahifasi 1 dan 300 gacha bo'lishi kerak.")

    reading_task = f"{reading_pages} bet" if "reading" in modules else None

    user.selected_modules_json = _dumps(modules)
    user.habits_json = json.dumps(habits_plan, ensure_ascii=False)
    user.sports_json = json.dumps(sports_plan, ensure_ascii=False)
    user.reading_book = reading_book if "reading" in modules else None
    user.reading_task = reading_task
    reminder_hours = [int(x) for x in payload.get("reminder_hours", [9, 14, 21]) if 0 <= int(x) <= 23]
    if len(reminder_hours) != 3:
        raise HTTPException(status_code=400, detail="exactly 3 reminder hours required")
    user.reminder_hours_json = ",".join([str(x) for x in sorted(set(reminder_hours))])
    user.onboarding_completed = True
    user.status = "setup_done"

    db.add(user)
    db.commit()

    return {
        "ok": True,
        "setup_completed": True,
        "modules": modules,
        "habits_count": len(habits_plan),
        "sports_count": len(sports_plan),
        "reading_book": user.reading_book,
        "reading_pages": reading_pages if "reading" in modules else 0,
    }


@router.post("/v1/app/payment/request")
def payment_request(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))
    if not user.registration_completed or not _is_setup_completed(user):
        raise HTTPException(status_code=400, detail="complete registration and setup first")

    user.payment_status = "pending"
    user.status = "awaiting_payment"
    db.add(user)
    db.commit()

    return {
        "ok": True,
        "payment_status": "pending",
        "amount_uzs": PAYMENT_AMOUNT_UZS,
        "note": "Admin profilga to'lov qilib, maxsus kodni mini appga kiriting.",
        "admin_username": ADMIN_CONTACT_USERNAME,
        "admin_url": f"https://t.me/{ADMIN_CONTACT_USERNAME}" if ADMIN_CONTACT_USERNAME else None,
        "admin_tg_deep_link": f"tg://resolve?domain={ADMIN_CONTACT_USERNAME}" if ADMIN_CONTACT_USERNAME else None,
        "provider": "manual_code",
    }


@router.post("/v1/app/payment/confirm")
def payment_confirm(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    if ADMIN_CONFIRM_TOKEN and x_admin_token != ADMIN_CONFIRM_TOKEN:
        raise HTTPException(status_code=403, detail="admin token invalid")

    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))
    if user.payment_status == "paid":
        return {"ok": True, "already_paid": True}

    _activate_user(user)
    db.add(user)
    db.commit()

    return {"ok": True, "payment_status": "paid", "marathon_started": True}


@router.post("/v1/app/payment/verify-code")
def payment_verify_code(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    tg_user_id = int(payload.get("tg_user_id", 0))
    code = str(payload.get("code", "")).strip().upper()
    if not tg_user_id or not code:
        raise HTTPException(status_code=400, detail="tg_user_id and code required")

    user = _get_user_or_404(db, tg_user_id)
    if user.payment_status == "paid":
        return {"ok": True, "already_paid": True, "payment_status": "paid", "marathon_started": True}

    ac = db.scalar(select(ActivationCode).where(ActivationCode.code == code))
    if not ac:
        raise HTTPException(status_code=404, detail="code not found")
    if ac.is_used:
        raise HTTPException(status_code=400, detail="code already used")
    if ac.target_tg_user_id and ac.target_tg_user_id != tg_user_id:
        raise HTTPException(status_code=403, detail="code belongs to another user")

    ac.is_used = True
    ac.used_by_tg_user_id = tg_user_id
    ac.used_at = datetime.utcnow()
    _activate_user(user)
    db.add_all([ac, user])
    db.commit()

    return {"ok": True, "payment_status": "paid", "marathon_started": True}


@router.post("/v1/app/payment/payme/merchant")
async def payment_payme_merchant(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if PAYMENT_MODE != "payme":
        raise HTTPException(status_code=410, detail="payme integration is disabled")

    if not _payme_auth_valid(request):
        payload = await request.json()
        return _payme_err(-32504, "Unauthorized", payload.get("id"))

    payload = await request.json()
    req_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "CheckPerformTransaction":
        amount = int(params.get("amount", 0) or 0)
        account = params.get("account") or {}
        tg_user_id = int(account.get("tg_user_id", 0) or 0)
        if amount != PAYMENT_AMOUNT_UZS * 100:
            return _payme_err(-31001, "Incorrect amount", req_id)
        user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if not user:
            return _payme_err(-31050, "User not found", req_id)
        if not user.registration_completed or not _is_setup_completed(user):
            return _payme_err(-31008, "User is not ready for payment", req_id)
        return _payme_ok({"allow": True}, req_id)

    if method == "CreateTransaction":
        provider_trans_id = str(params.get("id", ""))
        account = params.get("account") or {}
        tg_user_id = int(account.get("tg_user_id", 0) or 0)
        amount = int(params.get("amount", 0) or 0)
        if amount != PAYMENT_AMOUNT_UZS * 100:
            return _payme_err(-31001, "Incorrect amount", req_id)
        user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if not user:
            return _payme_err(-31050, "User not found", req_id)

        tx = db.scalar(
            select(PaymentTransaction).where(
                and_(
                    PaymentTransaction.provider == "payme",
                    PaymentTransaction.provider_trans_id == provider_trans_id,
                )
            )
        )
        if tx:
            return _payme_ok(
                {
                    "create_time": int(tx.created_at.timestamp() * 1000),
                    "transaction": tx.provider_trans_id,
                    "state": 1 if tx.status in {"created", "prepared"} else 2,
                },
                req_id,
            )

        tx = PaymentTransaction(
            user_id=user.id,
            provider="payme",
            provider_trans_id=provider_trans_id,
            merchant_trans_id=str(user.tg_user_id),
            amount_uzs=PAYMENT_AMOUNT_UZS,
            status="created",
        )
        user.payment_status = "pending"
        user.status = "awaiting_payment"
        db.add_all([tx, user])
        db.commit()
        return _payme_ok(
            {
                "create_time": int(tx.created_at.timestamp() * 1000),
                "transaction": tx.provider_trans_id,
                "state": 1,
            },
            req_id,
        )

    if method == "PerformTransaction":
        provider_trans_id = str(params.get("id", ""))
        tx = db.scalar(
            select(PaymentTransaction).where(
                and_(
                    PaymentTransaction.provider == "payme",
                    PaymentTransaction.provider_trans_id == provider_trans_id,
                )
            )
        )
        if not tx:
            return _payme_err(-31003, "Transaction not found", req_id)

        user = db.scalar(select(User).where(User.id == tx.user_id))
        if not user:
            return _payme_err(-31050, "User not found", req_id)

        if tx.status != "completed":
            tx.status = "completed"
            _activate_user(user)
            db.add_all([tx, user])
            db.commit()

        return _payme_ok(
            {
                "transaction": tx.provider_trans_id,
                "perform_time": int(datetime.utcnow().timestamp() * 1000),
                "state": 2,
            },
            req_id,
        )

    if method == "CancelTransaction":
        provider_trans_id = str(params.get("id", ""))
        reason = int(params.get("reason", 0) or 0)
        tx = db.scalar(
            select(PaymentTransaction).where(
                and_(
                    PaymentTransaction.provider == "payme",
                    PaymentTransaction.provider_trans_id == provider_trans_id,
                )
            )
        )
        if not tx:
            return _payme_err(-31003, "Transaction not found", req_id)

        tx.status = "cancelled"
        tx.click_error = reason
        user = db.scalar(select(User).where(User.id == tx.user_id))
        if user and user.payment_status != "paid":
            user.payment_status = "pending"
            db.add(user)
        db.add(tx)
        db.commit()
        return _payme_ok(
            {
                "transaction": tx.provider_trans_id,
                "cancel_time": int(datetime.utcnow().timestamp() * 1000),
                "state": -1,
            },
            req_id,
        )

    if method == "CheckTransaction":
        provider_trans_id = str(params.get("id", ""))
        tx = db.scalar(
            select(PaymentTransaction).where(
                and_(
                    PaymentTransaction.provider == "payme",
                    PaymentTransaction.provider_trans_id == provider_trans_id,
                )
            )
        )
        if not tx:
            return _payme_err(-31003, "Transaction not found", req_id)

        state = 2 if tx.status == "completed" else (-1 if tx.status == "cancelled" else 1)
        return _payme_ok(
            {
                "create_time": int(tx.created_at.timestamp() * 1000),
                "perform_time": int(tx.updated_at.timestamp() * 1000) if tx.status == "completed" else 0,
                "cancel_time": int(tx.updated_at.timestamp() * 1000) if tx.status == "cancelled" else 0,
                "transaction": tx.provider_trans_id,
                "state": state,
                "reason": tx.click_error or 0,
            },
            req_id,
        )

    return _payme_err(-32601, "Method not found", req_id)


@router.post("/v1/app/payment/click/callback")
def payment_click_callback(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    x_click_token: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    if PAYMENT_MODE != "click":
        raise HTTPException(status_code=410, detail="click integration is disabled")

    if CLICK_SECRET_TOKEN and x_click_token != CLICK_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="invalid callback token")

    tg_user_id = int(payload.get("transaction_param", 0))
    status = str(payload.get("status", "")).lower()
    amount = int(payload.get("amount", 0))
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="transaction_param required")

    user = _get_user_or_404(db, tg_user_id)
    if status not in {"paid", "success", "completed"}:
        user.payment_status = "pending"
        db.add(user)
        db.commit()
        return {"ok": True, "payment_status": user.payment_status}

    if amount and amount != PAYMENT_AMOUNT_UZS:
        raise HTTPException(status_code=400, detail="amount mismatch")

    if user.payment_status != "paid":
        _activate_user(user)
        db.add(user)
        db.commit()

    return {"ok": True, "payment_status": "paid", "marathon_started": True}


@router.post("/v1/app/payment/click/merchant")
async def payment_click_merchant(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    if PAYMENT_MODE != "click":
        raise HTTPException(status_code=410, detail="click integration is disabled")

    data = await _parse_click_payload(request)

    click_trans_id = str(data.get("click_trans_id", ""))
    service_id = str(data.get("service_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    merchant_prepare_id = int(data.get("merchant_prepare_id", "0") or 0)
    amount = str(data.get("amount", "0"))
    action = str(data.get("action", ""))
    sign_time = str(data.get("sign_time", ""))
    sign_string = str(data.get("sign_string", ""))
    error = int(data.get("error", "0") or 0)

    if not click_trans_id or not merchant_trans_id or action not in {"0", "1"}:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, 0, -2, "incorrect parameters")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -2, "incorrect parameters")
    if CLICK_SERVICE_ID and service_id != CLICK_SERVICE_ID:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, 0, -2, "service_id mismatch")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -2, "service_id mismatch")

    if not CLICK_SECRET_KEY:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, 0, -2, "merchant secret not configured")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -2, "merchant secret not configured")

    expected = (
        _click_sign_prepare(click_trans_id, merchant_trans_id, amount, action, sign_time)
        if action == "0"
        else _click_sign_complete(click_trans_id, merchant_trans_id, str(merchant_prepare_id), amount, action, sign_time)
    )
    if expected != sign_string:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -1, "sign check failed")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -1, "sign check failed")

    try:
        tg_user_id = int(merchant_trans_id)
    except Exception:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -5, "user not found")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -5, "user not found")

    user = db.scalar(select(User).where(User.tg_user_id == tg_user_id))
    if not user:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -5, "user not found")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -5, "user not found")

    try:
        amount_uzs = int(float(amount))
    except Exception:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -2, "incorrect amount")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -2, "incorrect amount")
    if amount_uzs != PAYMENT_AMOUNT_UZS:
        if action == "1":
            return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -2, "incorrect amount")
        return _click_prepare_response(click_trans_id, merchant_trans_id, 0, -2, "incorrect amount")

    tx = db.scalar(
        select(PaymentTransaction).where(
            and_(
                PaymentTransaction.provider == "click",
                PaymentTransaction.provider_trans_id == click_trans_id,
            )
        )
    )

    if action == "0":
        if user.payment_status == "paid":
            return _click_prepare_response(click_trans_id, merchant_trans_id, tx.id if tx else 0, -4, "already paid")

        if not tx:
            tx = PaymentTransaction(
                user_id=user.id,
                provider="click",
                provider_trans_id=click_trans_id,
                merchant_trans_id=merchant_trans_id,
                amount_uzs=amount_uzs,
                status="prepared",
                click_action=0,
                click_error=error,
                click_sign_time=sign_time,
            )
        else:
            tx.status = "prepared"
            tx.click_action = 0
            tx.click_error = error
            tx.click_sign_time = sign_time
        db.add(tx)
        user.payment_status = "pending"
        user.status = "awaiting_payment"
        db.add(user)
        db.commit()
        db.refresh(tx)
        return _click_prepare_response(click_trans_id, merchant_trans_id, tx.id, 0, "success")

    # action == 1 (complete)
    if merchant_prepare_id <= 0:
        return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -6, "merchant_prepare_id required")

    prepared_tx = db.scalar(
        select(PaymentTransaction).where(
            and_(
                PaymentTransaction.id == merchant_prepare_id,
                PaymentTransaction.provider == "click",
                PaymentTransaction.provider_trans_id == click_trans_id,
                PaymentTransaction.merchant_trans_id == merchant_trans_id,
            )
        )
    )
    if not prepared_tx:
        return _click_complete_response(click_trans_id, merchant_trans_id, merchant_prepare_id, -6, "transaction not found")

    tx = prepared_tx

    tx.click_action = 1
    tx.click_error = error
    tx.click_sign_time = sign_time

    if error < 0:
        tx.status = "cancelled" if error in {-5017, -9} else "failed"
        user.payment_status = "pending"
        db.add_all([tx, user])
        db.commit()
        db.refresh(tx)
        return _click_complete_response(click_trans_id, merchant_trans_id, tx.id, error, "failed")

    if tx.status == "completed" and user.payment_status == "paid":
        return _click_complete_response(click_trans_id, merchant_trans_id, tx.id, 0, "success")

    _activate_user(user)
    tx.status = "completed"
    db.add_all([tx, user])
    db.commit()
    db.refresh(tx)
    return _click_complete_response(click_trans_id, merchant_trans_id, tx.id, 0, "success")


@router.get("/v1/app/state/{tg_user_id}")
def app_state(tg_user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, tg_user_id)
    modules = _loads(user.selected_modules_json)
    habits_raw = _loads_any_json(user.habits_json, [])
    sports_raw = _loads_any_json(user.sports_json, [])
    if habits_raw and isinstance(habits_raw[0], str):
        habits_raw = [{"name": str(x), "days": ["daily"]} for x in habits_raw]
    if sports_raw and isinstance(sports_raw[0], str):
        sports_raw = [{"name": str(x), "days": ["daily"], "target_count": None} for x in sports_raw]
    reading_pages = 30
    if user.reading_task:
        try:
            reading_pages = int(str(user.reading_task).split()[0])
        except Exception:
            reading_pages = 30
    level = _level_from_points(user.rating_points or 0)
    _issue_certificate_if_ready(user)
    db.add(user)
    db.commit()

    return {
        "tg_user_id": user.tg_user_id,
        "full_name": user.full_name,
        "age": user.age,
        "location": user.location,
        "goal": user.goal,
        "pains": user.pains,
        "expectations": user.expectations,
        "registration_completed": user.registration_completed,
        "setup_completed": _is_setup_completed(user),
        "payment_status": user.payment_status,
        "is_active": _is_active(user),
        "rating_points": user.rating_points,
        "level": level,
        "marathon_day": _marathon_day(user),
        "marathon_days": user.marathon_days,
        "modules": modules,
        "habits": habits_raw,
        "sports": sports_raw,
        "reading_book": user.reading_book,
        "reading_task": user.reading_task,
        "reading_pages_per_day": reading_pages,
        "reminder_hours": [int(x) for x in (user.reminder_hours_json or "09,14,21").split(",") if x],
        "referral_count": get_referral_count(db, tg_user_id),
        "payment_mode": PAYMENT_MODE,
        "admin_username": ADMIN_CONTACT_USERNAME,
        "admin_url": f"https://t.me/{ADMIN_CONTACT_USERNAME}" if ADMIN_CONTACT_USERNAME else None,
        "certificate_issued": user.certificate_issued,
        "certificate_code": user.certificate_code,
    }


@router.get("/v1/app/daily/{tg_user_id}")
def app_daily(tg_user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, tg_user_id)
    if not _is_active(user):
        raise HTTPException(status_code=400, detail="marathon not active")

    plan = _daily_items_for_user(db, user)
    today = date.today()
    rows = db.execute(
        select(DailyModuleReport.module, DailyModuleReport.item_key, DailyModuleReport.is_done).where(
            and_(DailyModuleReport.user_id == user.id, DailyModuleReport.report_date == today)
        )
    ).all()
    done_map = {f"{m}:{k}": d for m, k, d in rows}

    return {
        "day": _marathon_day(user),
        "report_date": today.isoformat(),
        "plan": plan,
        "checked": done_map,
    }


@router.post("/v1/app/daily/report")
def app_daily_report(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))
    if not _is_active(user):
        raise HTTPException(status_code=400, detail="marathon not active")

    checked: Dict[str, List[str]] = payload.get("checked", {})
    if not isinstance(checked, dict):
        raise HTTPException(status_code=400, detail="checked must be object")

    report_date = date.today()
    plan = _daily_items_for_user(db, user)

    db.execute(
        delete(DailyModuleReport).where(
            and_(DailyModuleReport.user_id == user.id, DailyModuleReport.report_date == report_date)
        )
    )

    total = 0
    done = 0
    done_by_module: Dict[str, int] = {}
    total_by_module: Dict[str, int] = {}
    for module, items in plan.items():
        checked_set = set([str(x) for x in checked.get(module, [])])
        for item in items:
            is_done = item in checked_set
            db.add(
                DailyModuleReport(
                    user_id=user.id,
                    report_date=report_date,
                    module=module,
                    item_key=item,
                    is_done=is_done,
                )
            )
            total += 1
            total_by_module[module] = total_by_module.get(module, 0) + 1
            if is_done:
                done += 1
                done_by_module[module] = done_by_module.get(module, 0) + 1

    percent = int((done * 100) / total) if total else 0
    weighted_score = _weighted_daily_score(done_by_module, total_by_module)

    # Discipline model:
    # - >= 85 => strong day, bonus
    # - >= 70 => normal completed day
    # - < 70 => penalty, one-time freeze can protect streak
    points_gain = done
    if weighted_score >= 85:
        points_gain += 5
    user.rating_points += points_gain

    if weighted_score >= 70:
        user.current_streak += 1
    else:
        user.rating_points = max(0, user.rating_points - 3)
        user.missed_days_count = (user.missed_days_count or 0) + 1
        if user.current_streak > 0 and not user.streak_freeze_used:
            user.streak_freeze_used = True
        else:
            user.current_streak = 0

    user.last_report_date = report_date
    _issue_certificate_if_ready(user)
    db.add(user)
    db.commit()

    return {
        "ok": True,
        "done": done,
        "total": total,
        "percent": percent,
        "daily_score": weighted_score,
        "points_gain": points_gain,
        "rating": user.rating_points,
        "streak": user.current_streak,
        "streak_freeze_used": user.streak_freeze_used,
    }


@router.post("/v1/app/challenge/pick")
def app_challenge_pick(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, int(payload.get("tg_user_id", 0)))
    if _marathon_day(user) < 5:
        raise HTTPException(status_code=400, detail="challenge opens from day 5")

    numbers = payload.get("numbers", [])
    if not isinstance(numbers, list):
        raise HTTPException(status_code=400, detail="numbers must be list")
    try:
        nums = sorted(list({int(x) for x in numbers}))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid numbers") from exc

    if len(nums) != 3 or any(n < 1 or n > 30 for n in nums):
        raise HTTPException(status_code=400, detail="pick exactly 3 numbers in range 1..30")

    tasks = _challenge_tasks(nums)
    start = date.today()
    end = start + timedelta(days=4)

    db.add(
        Challenge(
            user_id=user.id,
            numbers_csv=",".join([str(x) for x in nums]),
            tasks_json=json.dumps(tasks, ensure_ascii=False),
            start_date=start,
            end_date=end,
            status="active",
        )
    )
    db.commit()

    return {"ok": True, "numbers": nums, "tasks": tasks, "deadline": end.isoformat()}


@router.get("/v1/app/progress/{tg_user_id}")
def app_progress(tg_user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, tg_user_id)
    start = date.today() - timedelta(days=24)

    rows = db.execute(
        select(
            DailyModuleReport.report_date,
            DailyModuleReport.module,
            func.count().label("total"),
            func.sum(func.cast(DailyModuleReport.is_done, Integer)).label("done"),
        )
        .where(and_(DailyModuleReport.user_id == user.id, DailyModuleReport.report_date >= start))
        .group_by(DailyModuleReport.report_date, DailyModuleReport.module)
        .order_by(DailyModuleReport.report_date.asc())
    ).all()

    table: List[Dict[str, Any]] = []
    module_done: Dict[str, int] = {}
    module_total: Dict[str, int] = {}

    for report_date, module, total, done in rows:
        done_val = int(done or 0)
        total_val = int(total or 0)
        table.append(
            {
                "date": report_date.isoformat(),
                "module": module,
                "done": done_val,
                "total": total_val,
                "percent": int((done_val * 100) / total_val) if total_val else 0,
            }
        )
        module_done[module] = module_done.get(module, 0) + done_val
        module_total[module] = module_total.get(module, 0) + total_val

    module_percent = {
        module: (int((module_done[module] * 100) / module_total[module]) if module_total[module] else 0)
        for module in module_total
    }

    by_date: Dict[str, Dict[str, int]] = {}
    for row in table:
        date_key = row["date"]
        if date_key not in by_date:
            by_date[date_key] = {"done": 0, "total": 0}
        by_date[date_key]["done"] += int(row["done"])
        by_date[date_key]["total"] += int(row["total"])

    daily_scores: Dict[str, int] = {}
    for date_key, agg in by_date.items():
        # Reconstruct with global ratio for lightweight board preview
        total_val = int(agg["total"])
        done_val = int(agg["done"])
        daily_scores[date_key] = int((done_val * 100) / total_val) if total_val else 0

    chain: list[Dict[str, Any]] = []
    if user.marathon_start_date:
        for offset in range(user.marathon_days):
            d = user.marathon_start_date + timedelta(days=offset)
            key = d.isoformat()
            score = daily_scores.get(key)
            chain.append(
                {
                    "date": key,
                    "day": offset + 1,
                    "score": score if score is not None else 0,
                    "status": "done" if (score is not None and score >= 70) else ("partial" if score is not None else "empty"),
                }
            )

    return {
        "rating_points": user.rating_points,
        "current_streak": user.current_streak,
        "level": _level_from_points(user.rating_points or 0),
        "today_remaining": max(0, 100 - daily_scores.get(date.today().isoformat(), 0)),
        "module_percent": module_percent,
        "daily_scores": daily_scores,
        "chain": chain,
        "table": table,
    }


@router.get("/v1/app/leaderboard")
def app_leaderboard(limit: int = 10, db: Session = Depends(get_db)) -> Dict[str, Any]:
    limit = max(3, min(limit, 50))
    users = list(
        db.scalars(
            select(User)
            .where(User.payment_status == "paid")
            .order_by(User.rating_points.desc(), User.current_streak.desc())
            .limit(limit)
        )
    )
    return {
        "count": len(users),
        "items": [
            {
                "rank": idx + 1,
                "tg_user_id": u.tg_user_id,
                "name": u.full_name or u.first_name or u.username or f"User {u.tg_user_id}",
                "username": u.username,
                "rating_points": u.rating_points,
                "streak": u.current_streak,
                "level": _level_from_points(u.rating_points or 0),
            }
            for idx, u in enumerate(users)
        ],
    }


@router.get("/v1/app/certificate/{tg_user_id}")
def app_certificate(tg_user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, tg_user_id)
    _issue_certificate_if_ready(user)
    db.add(user)
    db.commit()
    if not user.certificate_issued:
        raise HTTPException(status_code=400, detail="certificate not ready")
    return {
        "tg_user_id": user.tg_user_id,
        "full_name": user.full_name,
        "certificate_code": user.certificate_code,
        "issued": user.certificate_issued,
        "rating_points": user.rating_points,
        "streak": user.current_streak,
        "level": _level_from_points(user.rating_points or 0),
        "text": (
            f"Sertifikat\\n"
            f"Ism: {user.full_name or user.first_name or user.tg_user_id}\\n"
            f"Kod: {user.certificate_code}\\n"
            f"Natija: {user.rating_points} ball | streak {user.current_streak}"
        ),
    }


@router.get("/v1/profile/{tg_user_id}")
def profile(tg_user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user = _get_user_or_404(db, tg_user_id)
    day_no = _marathon_day(user)
    _issue_certificate_if_ready(user)
    db.add(user)
    db.commit()
    return {
        "tg_user_id": tg_user_id,
        "full_name": user.full_name,
        "age": user.age,
        "location": user.location,
        "goal": user.goal,
        "pains": user.pains,
        "expectations": user.expectations,
        "status": user.status,
        "is_paid": user.is_paid,
        "onboarding_completed": user.onboarding_completed,
        "marathon_days": user.marathon_days,
        "marathon_day_no": day_no,
        "remaining_days": max(0, user.marathon_days - day_no),
        "rating_points": user.rating_points,
        "current_streak": user.current_streak,
        "level": _level_from_points(user.rating_points or 0),
        "certificate_issued": user.certificate_issued,
        "certificate_code": user.certificate_code,
        "referral_count": get_referral_count(db, tg_user_id),
    }
