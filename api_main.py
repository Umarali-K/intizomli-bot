from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.crud import seed_habits_if_empty
from app.db import SessionLocal, engine
from app.models import Base

app = FastAPI(title="Intizomli API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_habits_if_empty(db)
