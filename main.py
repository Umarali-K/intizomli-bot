import json
import os
import random
import string
from datetime import time as dtime
from pathlib import Path
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.crud import create_referral, get_referral_count, get_reportable_users, get_user_by_tg_id, upsert_user
from app.db import SessionLocal
from app.models import ActivationCode

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://intizomli-miniapp.vercel.app")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "http://localhost:8000")
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


async def module_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    hour = context.job.data.get("hour") if context.job else None
    with SessionLocal() as db:
        users = get_reportable_users(db)

    for user in users:
        modules = _user_modules(user)
        if not modules:
            continue
        msg = (
            "⏰ *Eslatma*\n\n"
            f"Hozirgi slot: *{hour}:00*\n"
            f"Bugungi modullar: {', '.join(modules)}\n"
            "Mini App orqali checkbox bilan hisobot yuboring."
        )
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


def run() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("code", create_code))
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

    print("✅ Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    run()
