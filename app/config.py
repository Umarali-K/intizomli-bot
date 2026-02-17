import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    MINIAPP_URL: str = os.getenv("MINIAPP_URL", "https://intizomli-miniapp.vercel.app")
    API_PUBLIC_URL: str = os.getenv("API_PUBLIC_URL", "http://localhost:8000")
    ADMIN_CONTACT_USERNAME: str = os.getenv("ADMIN_CONTACT_USERNAME", "").strip().lstrip("@")
    ADMIN_TG_IDS: str = os.getenv("ADMIN_TG_IDS", "")
    ADMIN_API_TOKEN: str = os.getenv("ADMIN_API_TOKEN", "").strip()
    ADMIN_CONFIRM_TOKEN: str = os.getenv("ADMIN_CONFIRM_TOKEN", "").strip()
    ACTIVATION_CODE_TTL_HOURS: int = int(os.getenv("ACTIVATION_CODE_TTL_HOURS", "720"))
    RETENTION_DAYS: str = os.getenv("RETENTION_DAYS", "2,3,5")
    PAYMENT_MODE: str = os.getenv("PAYMENT_MODE", "manual_code").strip().lower()
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./intizomli.db")
    AUTO_CREATE_SCHEMA: bool = os.getenv("AUTO_CREATE_SCHEMA", "0") == "1"
    CORS_ORIGINS: list[str] = [
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "*").split(",")
        if item.strip()
    ]


settings = Settings()
