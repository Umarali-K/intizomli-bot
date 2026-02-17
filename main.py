import json
import os
import random
import string
from datetime import time as dtime
from datetime import date
from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import and_, delete, func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.crud import create_referral, get_referral_count, get_reportable_users, get_user_by_tg_id, upsert_user
from app.db import SessionLocal
from app.models import ActivationCode, Challenge, DailyModuleReport, PaymentTransaction, Referral, User

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

def _clean_env_url(value: str, key_name: str) -> str:
    raw = (value or "").strip()
    lower = raw.lower()
    prefix = f"{key_name.lower()}="
    if lower.startswith(prefix):
        raw = raw[len(prefix) :].strip()
    return raw


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MINIAPP_URL = _clean_env_url(os.getenv("MINIAPP_URL", "https://intizomli-miniapp.vercel.app"), "MINIAPP_URL")
API_PUBLIC_URL = _clean_env_url(os.getenv("API_PUBLIC_URL", "http://localhost:8000"), "API_PUBLIC_URL")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Asia/Tashkent")
REMINDER_HOURS = [int(x) for x in os.getenv("REMINDER_HOURS", "9,14,21").split(",") if x.strip()]
ADMIN_TG_IDS = {int(x.strip()) for x in os.getenv("ADMIN_TG_IDS", "").split(",") if x.strip().isdigit()}


def build_miniapp_url() -> str:
    parts = urlsplit(MINIAPP_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["api"] = API_PUBLIC_URL
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📱 Mini Appni ochish", web_app=WebAppInfo(url=build_miniapp_url()))],
            [InlineKeyboardButton("🤝 Referal", callback_data="menu:ref")],
            [InlineKeyboardButton("👤 Profil", callback_data="menu:profile")],
            [InlineKeyboardButton("❓ FAQ", callback_data="menu:faq")],
            [InlineKeyboardButton("💬 Qatnashganlar fikri", callback_data="menu:reviews")],
        ]
    )


def _user_modules(user) -> List[str]:
    if not user or not user.selected_modules_json:
        return []
    try:
        data = json.loads(user.selected_modules_json)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        return []
    return []


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_TG_IDS


def _gen_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _reminder_slot(hour: int) -> str:
    hours = sorted(REMINDER_HOURS[:3]) if REMINDER_HOURS else [9, 14, 21]
    if hour == hours[0]:
        return "morning"
    if len(hours) > 1 and hour == hours[1]:
        return "midday"
    return "night"


def _user_label(user: User) -> str:
    name = (user.full_name or "").strip() or (user.first_name or "").strip() or (user.username or "").strip()
    if user.username:
        return f"{name} (@{user.username}) [{user.tg_user_id}]"
    return f"{name} [{user.tg_user_id}]"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    ref_code = context.args[0] if context.args else ""

    with SessionLocal() as db:
        user = upsert_user(db, tg_user.id, tg_user.username, tg_user.first_name)
        if ref_code.startswith("ref_"):
            try:
                referrer_id = int(ref_code.replace("ref_", "", 1))
                create_referral(db, referrer_id, tg_user.id)
            except ValueError:
                pass

    state = "aktiv ✅" if user.payment_status == "paid" else "to'lov kutilmoqda"
    await update.message.reply_text(
        "🔥 *INTIZOMLI ERKAK*\n\n"
        "Asosiy jarayon endi Mini App ichida: ro'yxatdan o'tish → modul sozlash → to'lov → marafon.\n\n"
        f"Holat: *{state}*\n"
        "Mini Appni oching 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    with SessionLocal() as db:
        user = upsert_user(db, q.from_user.id, q.from_user.username, q.from_user.first_name)

    key = q.data.split(":", 1)[1]

    if key == "ref":
        with SessionLocal() as db:
            ref_count = get_referral_count(db, q.from_user.id)
        bot_username = context.bot.username or "YOUR_BOT_USERNAME"
        text = (
            "🤝 *Referal*\n\n"
            "Sizning havolangiz:\n"
            f"`t.me/{bot_username}?start=ref_{q.from_user.id}`\n\n"
            f"Taklif qilganlar: *{ref_count}*"
        )
    elif key == "profile":
        modules = ", ".join(_user_modules(user)) or "-"
        text = (
            "👤 *Profil*\n\n"
            f"ID: `{q.from_user.id}`\n"
            f"To'lov holati: *{user.payment_status}*\n"
            f"Reyting: *{user.rating_points}*\n"
            f"Streak: *{user.current_streak}*\n"
            f"Modullar: {modules}"
        )
    elif key == "faq":
        text = (
            "❓ *FAQ*\n\n"
            "1) Marafon qachon boshlanadi? — To'lov admin tomonidan tasdiqlangach.\n"
            "2) Qayerda yuritiladi? — To'liq Mini App ichida.\n"
            "3) Challenge qachon ochiladi? — 5-kundan boshlab.\n"
            "4) Eslatmalar? — Kuniga 3 mahal."
        )
    elif key == "reviews":
        text = (
            "💬 *Qatnashganlar fikri*\n\n"
            "- Hisobot majburiyligi tufayli intizom oshdi.\n"
            "- Mini Appdagi doska natijani aniq ko'rsatdi."
        )
    else:
        text = "Mini Appni ochib davom eting."

    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())


async def on_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wad = update.effective_message.web_app_data
    if not wad:
        return

    try:
        payload = json.loads(wad.data)
    except Exception:
        await update.message.reply_text("❌ Mini App data xato.")
        return

    if payload.get("type") == "daily_report_submitted":
        await update.message.reply_text("✅ Hisobot qabul qilindi.")


async def create_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return

    if not context.args:
        await update.message.reply_text("Foydalanish: /code <tg_user_id>")
        return

    try:
        target_tg_user_id = int(context.args[0])
    except Exception:
        await update.message.reply_text("❌ tg_user_id noto'g'ri.")
        return

    code = _gen_code()
    with SessionLocal() as db:
        # Ensure unique code.
        while db.scalar(select(ActivationCode).where(ActivationCode.code == code)):
            code = _gen_code()
        db.add(
            ActivationCode(
                code=code,
                target_tg_user_id=target_tg_user_id,
                created_by_tg_user_id=user_id,
                is_used=False,
            )
        )
        db.commit()

    await update.message.reply_text(
        f"✅ Aktivatsiya kodi yaratildi:\n`{code}`\n\nUser: `{target_tg_user_id}`",
        parse_mode="Markdown",
    )


async def create_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return

    count = 200
    if context.args:
        try:
            count = int(context.args[0])
        except Exception:
            await update.message.reply_text("Foydalanish: /codes <count>")
            return
    if count < 1 or count > 500:
        await update.message.reply_text("Count 1..500 oralig'ida bo'lsin.")
        return

    created: List[str] = []
    with SessionLocal() as db:
        for _ in range(count):
            code = _gen_code()
            while db.scalar(select(ActivationCode).where(ActivationCode.code == code)):
                code = _gen_code()
            db.add(
                ActivationCode(
                    code=code,
                    target_tg_user_id=None,
                    created_by_tg_user_id=user_id,
                    is_used=False,
                )
            )
            created.append(code)
        db.commit()

    text = "✅ Maxsus kodlar yaratildi:\n\n" + "\n".join(created)
    for i in range(0, len(text), 3900):
        await update.message.reply_text(text[i : i + 3900])


async def reset_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not tg_user:
        return

    with SessionLocal() as db:
        user = get_user_by_tg_id(db, tg_user.id)
        if not user:
            await update.message.reply_text("Siz uchun saqlangan profil topilmadi. /start bosing.")
            return

        db.execute(delete(DailyModuleReport).where(DailyModuleReport.user_id == user.id))
        db.execute(delete(Challenge).where(Challenge.user_id == user.id))
        db.execute(delete(PaymentTransaction).where(PaymentTransaction.user_id == user.id))
        db.execute(
            delete(Referral).where(
                and_(
                    Referral.invited_tg_user_id == tg_user.id,
                )
            )
        )
        db.execute(
            delete(Referral).where(
                and_(
                    Referral.referrer_tg_user_id == tg_user.id,
                )
            )
        )

        used_codes = db.scalars(select(ActivationCode).where(ActivationCode.used_by_tg_user_id == tg_user.id)).all()
        for ac in used_codes:
            ac.is_used = False
            ac.used_by_tg_user_id = None
            ac.used_at = None
            db.add(ac)

        user.status = "unpaid"
        user.is_paid = False
        user.onboarding_completed = False
        user.rating_points = 0
        user.current_streak = 0
        user.marathon_start_date = None
        user.full_name = None
        user.age = None
        user.location = None
        user.goal = None
        user.pains = None
        user.expectations = None
        user.registration_completed = False
        user.selected_modules_json = None
        user.habits_json = None
        user.sports_json = None
        user.reading_book = None
        user.reading_task = None
        user.reminder_hours_json = None
        user.payment_status = "unpaid"
        user.payment_confirmed_at = None
        user.streak_freeze_used = False
        user.missed_days_count = 0
        user.last_report_date = None
        user.last_weekly_review_sent_at = None
        user.certificate_issued = False
        user.certificate_code = None
        db.add(user)
        db.commit()

    await update.message.reply_text(
        "✅ Profilingiz reset qilindi.\n"
        "Endi /start bosib 0 dan ro'yxatdan o'tishingiz mumkin."
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return

    today = date.today()
    with SessionLocal() as db:
        total_users = db.scalar(select(func.count()).select_from(User)) or 0
        paid_users = db.scalar(select(func.count()).select_from(User).where(User.payment_status == "paid")) or 0
        active_users = db.scalar(select(func.count()).select_from(User).where(User.status == "active")) or 0
        paid_user_rows = list(db.scalars(select(User).where(User.payment_status == "paid").order_by(User.created_at.desc())))
        submitted_internal_ids = set(
            db.scalars(
                select(DailyModuleReport.user_id)
                .where(DailyModuleReport.report_date == today)
                .group_by(DailyModuleReport.user_id)
            )
        )

    submitted = [u for u in paid_user_rows if u.id in submitted_internal_ids]
    missed = [u for u in paid_user_rows if u.id not in submitted_internal_ids]

    text = (
        "📊 *Admin statistika*\n\n"
        f"Jami userlar: *{total_users}*\n"
        f"To'laganlar: *{paid_users}*\n"
        f"Aktivlar: *{active_users}*\n"
        f"Bugun hisobot yuborganlar: *{len(submitted)}*\n"
        f"Bugun hisobot yubormaganlar: *{len(missed)}*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

    submitted_lines = [f"- {_user_label(u)}" for u in submitted[:50]]
    missed_lines = [f"- {_user_label(u)}" for u in missed[:50]]

    await update.message.reply_text(
        "✅ *Bugun yuborganlar*:\n" + ("\n".join(submitted_lines) if submitted_lines else "- yo'q"),
        parse_mode="Markdown",
    )
    await update.message.reply_text(
        "⚠️ *Bugun yubormaganlar*:\n" + ("\n".join(missed_lines) if missed_lines else "- yo'q"),
        parse_mode="Markdown",
    )


async def admin_missed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return

    target_date = date.today()
    if context.args:
        try:
            target_date = date.fromisoformat(context.args[0])
        except Exception:
            await update.message.reply_text("Foydalanish: /missed yoki /missed YYYY-MM-DD")
            return

    with SessionLocal() as db:
        paid_users = list(db.scalars(select(User).where(User.payment_status == "paid")))
        submitted_ids = set(
            db.scalars(
                select(DailyModuleReport.user_id)
                .where(DailyModuleReport.report_date == target_date)
                .group_by(DailyModuleReport.user_id)
            )
        )
        missed = [u for u in paid_users if u.id not in submitted_ids]

    lines = [f"- {_user_label(u)}" for u in missed] or ["- yo'q"]
    header = f"⚠️ *Hisobot yubormaganlar* ({target_date.isoformat()})\nSoni: *{len(missed)}*\n\n"
    text = header + "\n".join(lines)
    for i in range(0, len(text), 3900):
        await update.message.reply_text(text[i : i + 3900], parse_mode="Markdown")


async def admin_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if not _is_admin(admin_id):
        await update.message.reply_text("❌ Siz admin emassiz.")
        return

    if not context.args:
        await update.message.reply_text("Foydalanish: /kick <tg_user_id>")
        return

    try:
        target_tg_id = int(context.args[0])
    except Exception:
        await update.message.reply_text("❌ tg_user_id noto'g'ri.")
        return

    with SessionLocal() as db:
        user = get_user_by_tg_id(db, target_tg_id)
        if not user:
            await update.message.reply_text("❌ User topilmadi.")
            return
        user.status = "kicked"
        user.is_paid = False
        user.payment_status = "kicked"
        user.onboarding_completed = False
        db.add(user)
        db.commit()
        label = _user_label(user)

    await update.message.reply_text(f"⛔️ Marafondan chiqarildi:\n{label}")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as db:
        users = list(
            db.scalars(
                select(User)
                .where(User.payment_status == "paid")
                .order_by(User.rating_points.desc(), User.current_streak.desc())
                .limit(10)
            )
        )
    if not users:
        await update.message.reply_text("Hali leaderboard bo'sh.")
        return
    lines = []
    for i, u in enumerate(users, start=1):
        name = (u.full_name or u.first_name or u.username or f"User {u.tg_user_id}").strip()
        lines.append(f"{i}. {name} — {u.rating_points} ball | streak {u.current_streak}")
    await update.message.reply_text("🏆 *Top 10 Leaderboard*\n\n" + "\n".join(lines), parse_mode="Markdown")


async def weekly_review_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Sunday review; safe to run daily on schedule, exits on non-Sunday.
    today = date.today()
    if today.weekday() != 6:
        return

    start = today.fromordinal(today.toordinal() - 6)
    with SessionLocal() as db:
        users = get_reportable_users(db)
        for user in users:
            done = db.scalar(
                select(func.count()).select_from(DailyModuleReport).where(
                    and_(
                        DailyModuleReport.user_id == user.id,
                        DailyModuleReport.report_date >= start,
                        DailyModuleReport.report_date <= today,
                        DailyModuleReport.is_done.is_(True),
                    )
                )
            ) or 0
            total = db.scalar(
                select(func.count()).select_from(DailyModuleReport).where(
                    and_(
                        DailyModuleReport.user_id == user.id,
                        DailyModuleReport.report_date >= start,
                        DailyModuleReport.report_date <= today,
                    )
                )
            ) or 0
            percent = int((done * 100) / total) if total else 0
            msg = (
                "📅 *Haftalik review*\n\n"
                f"Sana: {start.isoformat()} — {today.isoformat()}\n"
                f"Bajarilgan: {done}/{total}\n"
                f"Haftalik foiz: {percent}%\n"
                f"Joriy streak: {user.current_streak}\n\n"
                "Kelasi haftaga maqsadni aniq qo'ying va ritmni ushlang."
            )
            try:
                await context.bot.send_message(chat_id=user.tg_user_id, text=msg, parse_mode="Markdown")
            except Exception:
                continue


async def module_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    hour = context.job.data.get("hour") if context.job else None
    slot = _reminder_slot(int(hour)) if hour is not None else "midday"
    with SessionLocal() as db:
        users = get_reportable_users(db)
        for user in users:
            modules = _user_modules(user)
            if not modules:
                continue
            today = date.today()
            total_today = db.scalar(
                select(func.count()).select_from(DailyModuleReport).where(
                    and_(DailyModuleReport.user_id == user.id, DailyModuleReport.report_date == today)
                )
            ) or 0
            done_today = db.scalar(
                select(func.count()).select_from(DailyModuleReport).where(
                    and_(
                        DailyModuleReport.user_id == user.id,
                        DailyModuleReport.report_date == today,
                        DailyModuleReport.is_done.is_(True),
                    )
                )
            ) or 0
            pending_hint = ""
            if slot == "night":
                if total_today == 0:
                    pending_hint = "\n\n⚠️ Bugun hali hisobot yuborilmadi."
                elif done_today < total_today:
                    pending_hint = f"\n\n⚠️ Hisobot tugallanmagan: {done_today}/{total_today}"

            if slot == "morning":
                msg = (
                    "🌅 *Tonggi eslatma*\n\n"
                    "Yangi kun boshlandi. Bugungi odatlar, sport va mutolaani bajarishni boshlang."
                )
            elif slot == "midday":
                msg = (
                    "🕑 *Kun yarmidagi eslatma*\n\n"
                    "Rejadan ortda qolmang, bugungi vazifalarni davom ettiring."
                )
            else:
                msg = (
                    "🌙 *Tungi eslatma*\n\n"
                    "Kun yakunlandi. Mini App'da bugungi hisobotni yuborishni unutmang."
                )
            msg = msg + f"\n\nBugungi modullar: {', '.join(modules)}{pending_hint}"
            try:
                await context.bot.send_message(
                    chat_id=user.tg_user_id,
                    text=msg,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📱 Mini Appni ochish", web_app=WebAppInfo(url=build_miniapp_url()))]]
                    ),
                )
            except Exception:
                continue

        if slot == "night" and ADMIN_TG_IDS:
            paid_users = list(db.scalars(select(User).where(User.payment_status == "paid")))
            submitted_ids = set(
                db.scalars(
                    select(DailyModuleReport.user_id)
                    .where(DailyModuleReport.report_date == date.today())
                    .group_by(DailyModuleReport.user_id)
                )
            )
            missed = [u for u in paid_users if u.id not in submitted_ids]
            if missed:
                lines = [f"- {_user_label(u)}" for u in missed[:50]]
                admin_text = (
                    f"🚨 *Mentor ping*\\n\\n"
                    f"Bugun hisobot yubormaganlar soni: *{len(missed)}*\\n\\n"
                    + "\\n".join(lines)
                )
                for admin_tg_id in ADMIN_TG_IDS:
                    try:
                        await context.bot.send_message(chat_id=admin_tg_id, text=admin_text, parse_mode="Markdown")
                    except Exception:
                        continue


def run() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("code", create_code))
    app.add_handler(CommandHandler("codes", create_codes))
    app.add_handler(CommandHandler("resetme", reset_me))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("missed", admin_missed))
    app.add_handler(CommandHandler("kick", admin_kick))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CallbackQueryHandler(on_menu, pattern=r"^menu:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp_data))

    if app.job_queue:
        try:
            tz = ZoneInfo(BOT_TIMEZONE)
        except Exception:
            tz = ZoneInfo("UTC")

        for hr in REMINDER_HOURS[:3]:
            app.job_queue.run_daily(
                module_reminder_job,
                time=dtime(hour=int(hr), minute=0, tzinfo=tz),
                name=f"module-reminder-{hr}",
                data={"hour": int(hr)},
            )
        app.job_queue.run_daily(
            weekly_review_job,
            time=dtime(hour=21, minute=30, tzinfo=tz),
            name="weekly-review",
            data={"kind": "weekly-review"},
        )

    print("✅ Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    run()
