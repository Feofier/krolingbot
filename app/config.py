import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://example.com/miniapp")  # URL Mini App из BotFather
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./krolingo.db")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # если пусто — long polling

FREE_DAILY_LESSONS = 2

PLANS = {
    "week": {"days": 7, "stars": 50, "title": "Подписка 7 дней"},
    "month": {"days": 30, "stars": 150, "title": "Подписка 30 дней"},
    "halfyear": {"days": 180, "stars": 700, "title": "Подписка 180 дней"},
}
