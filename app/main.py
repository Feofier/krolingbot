import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .bot.handlers import setup_dp
from .config import BOT_TOKEN, MINIAPP_URL, WEBHOOK_URL
from .db import Base, SessionLocal, engine
from .api.routes import router as api_router
from .lessons.seed import seed_if_empty

logging.basicConfig(level=logging.INFO)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # миграции без Alembic: добавляем новые колонки, если их нет
        try:
            await conn.execute(text(
                "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS intro JSON"))
        except Exception:
            pass
    async with SessionLocal() as session:
        await seed_if_empty(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # сид и миграции — в фоне, чтобы деплой не падал по таймауту healthcheck
    init_task = asyncio.create_task(init_db())
    app.state.bot = None
    if not BOT_TOKEN:
        yield
        return
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = setup_dp()
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL.rstrip("/") + "/webhook")
        app.state.bot = bot
        app.state.dp = dp
        yield
        await bot.session.close()
        return

    polling_task = asyncio.create_task(dp.start_polling(bot))
    app.state.bot = bot
    yield
    polling_task.cancel()
    init_task.cancel()
    await bot.session.close()


app = FastAPI(title="Krolingo", lifespan=lifespan)
app.include_router(api_router)
app.mount("/miniapp", StaticFiles(directory=MINIAPP_DIR, html=True), name="miniapp")


@app.get("/")
async def root():
    return {"app": "Krolingo", "miniapp": MINIAPP_URL}


@app.exception_handler(Exception)
async def debug_errors(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"error": repr(exc), "trace": traceback.format_exc()[-2000:]})


@app.get("/debug/env")
async def debug_env():
    import os
    return {"DB_URL": os.environ.get("DB_URL", "<unset>"),
            "keys": sorted(k for k in os.environ if k in
                           ("BOT_TOKEN", "WEBHOOK_URL", "MINIAPP_URL", "DB_URL"))}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    from aiogram.types import Update
    bot = request.app.state.bot
    dp = request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
