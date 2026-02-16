# Intizomli Bot + Mini App

Asosiy jarayon to'liq **Mini App** ichida:

1. Ro'yxatdan o'tish
2. Modullarni sozlash
3. To'lov (admin profilga)
4. Admin bergan maxsus kodni kiritish
5. Marafon ochilishi

## Lokal ishga tushirish

```bash
cd /Users/umarali/intizomli-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

### `.env`

```env
BOT_TOKEN=your_bot_token
MINIAPP_URL=https://intizomli-miniapp.vercel.app
API_PUBLIC_URL=http://localhost:8000
DATABASE_URL=sqlite:///./intizomli.db
AUTO_CREATE_SCHEMA=0
CORS_ORIGINS=*
BOT_TIMEZONE=Asia/Tashkent
REMINDER_HOURS=9,14,21

# To'lov usuli
PAYMENT_MODE=manual_code
ADMIN_CONTACT_USERNAME=your_admin_username

# Bot adminlari (kod chiqarish uchun)
ADMIN_TG_IDS=123456789,987654321
```

### API

```bash
source .venv/bin/activate
uvicorn api_main:app --reload
```

### Bot

```bash
source .venv/bin/activate
python main.py
```

## Manual code payment flow

- User mini appda `Adminga o'tish` tugmasini bosadi
- To'lov admin profilida amalga oshiriladi
- Admin botda kod yaratadi: `/code <tg_user_id>`
- User mini appda kodni kiritadi (`/v1/app/payment/verify-code`)
- Kod to'g'ri bo'lsa marafon `paid + active`

## Asosiy endpointlar

- `POST /v1/app/bootstrap`
- `POST /v1/app/register`
- `POST /v1/app/setup`
- `POST /v1/app/payment/request`
- `POST /v1/app/payment/verify-code`
- `GET /v1/app/state/{tg_user_id}`
- `GET /v1/app/daily/{tg_user_id}`
- `POST /v1/app/daily/report`
- `POST /v1/app/challenge/pick`
- `GET /v1/app/progress/{tg_user_id}`

## Admin komandasi

- `/code <tg_user_id>` — shu user uchun bir martalik aktivatsiya kodi yaratadi
