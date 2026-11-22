import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

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
    async with SessionLocal() as session:
        await seed_if_empty(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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
