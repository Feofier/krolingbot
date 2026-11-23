import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .bot.handlers import BOT_COMMANDS, setup_dp
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
            await conn.execute(text(
                "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS theory JSON"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS ui_language VARCHAR(8) DEFAULT 'ru'"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_lang_change TIMESTAMP"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_remind DATE"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(64)"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code VARCHAR(32)"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by BIGINT"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_bonus_given BOOLEAN DEFAULT false"))
            await conn.execute(text(
                "UPDATE users SET ref_code = 'u' || telegram_id WHERE ref_code IS NULL"))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_lessons INTEGER DEFAULT 0"))
        except Exception:
            pass
    async with SessionLocal() as session:
        await seed_if_empty(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # сид и миграции — в фоне, чтобы деплой не падал по таймауту healthcheck
    async def _init():
        try:
            await init_db()
        except Exception:
            logging.exception("init_db failed")
    init_task = asyncio.create_task(_init())
    app.state.bot = None
    if not BOT_TOKEN:
        yield
        return
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = setup_dp()
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL.rstrip("/") + "/webhook")
        await bot.set_my_commands(BOT_COMMANDS)
        from .bot.handlers import reminder_loop
        reminder_task = asyncio.create_task(reminder_loop(bot))
        app.state.bot = bot
        app.state.dp = dp
        yield
        reminder_task.cancel()
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


@app.post("/webhook")
async def telegram_webhook(request: Request):
    from aiogram.types import Update
    bot = request.app.state.bot
    dp = request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
