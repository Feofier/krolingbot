import hashlib
import hmac
import json
import os
import urllib.parse

os.environ["BOT_TOKEN"] = "test-token-123"
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
from sqlalchemy import select
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import validate_init_data
from app.db import Base, engine, SessionLocal
from app.main import app
from app.models import Exercise, Language, Lesson, User, UserLanguage
from app.services import (can_start_lesson, complete_lesson,
                          get_or_create_user, grant_subscription)


def make_init_data(tg_id: int = 1) -> str:
    user = json.dumps({"id": tg_id, "first_name": "Test"})
    data = {"query_id": "q1", "user": user, "auth_date": "1700000000"}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", b"test-token-123", hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(data)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        from app.lessons.seed import seed_if_empty
        await seed_if_empty(s)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_validate_init_data_ok():
    user = validate_init_data(make_init_data(42))
    assert user["id"] == 42


def test_validate_init_data_bad():
    with pytest.raises(Exception):
        validate_init_data("user={}&hash=deadbeef")


@pytest.mark.asyncio
async def test_daily_limit_and_subscription():
    async with SessionLocal() as s:
        user = await get_or_create_user(s, 1)
        assert await can_start_lesson(s, user.id)
        await grant_subscription(s, user.id, "month", 30)
        # с подпиской лимита нет — пройдём 3 урока
        lang = (await s.execute(__import__("sqlalchemy").select(Language)
                                .where(Language.code == "en"))).scalar_one()
        lessons = (await s.execute(__import__("sqlalchemy").select(Lesson)
                                   .where(Lesson.language_id == lang.id)
                                   .order_by(Lesson.number))).scalars().all()
        ul = UserLanguage(user_id=user.id, language_id=lang.id)
        s.add(ul)
        await s.commit()
        for lesson in lessons[:3]:
            await complete_lesson(s, user, ul, lesson)
        assert await can_start_lesson(s, user.id)


@pytest.mark.asyncio
async def test_free_limit_blocks_third_lesson():
    async with SessionLocal() as s:
        user = await get_or_create_user(s, 2)
        lang = (await s.execute(__import__("sqlalchemy").select(Language)
                                .where(Language.code == "en"))).scalar_one()
        lessons = (await s.execute(__import__("sqlalchemy").select(Lesson)
                                   .where(Lesson.language_id == lang.id)
                                   .order_by(Lesson.number))).scalars().all()
        ul = UserLanguage(user_id=user.id, language_id=lang.id)
        s.add(ul)
        await s.commit()
        await complete_lesson(s, user, ul, lessons[0])
        await complete_lesson(s, user, ul, lessons[1])
        assert not await can_start_lesson(s, user.id)


@pytest.mark.asyncio
async def test_api_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"X-Init-Data": make_init_data(7)}
        r = await client.get("/api/me", headers=h)
        assert r.status_code == 200
        langs = (await client.get("/api/languages", headers=h)).json()
        assert len(langs) == 2
        await client.post("/api/languages", headers=h,
                          json={"language_id": langs[0]["id"]})
        lesson = (await client.get(f"/api/lesson/{langs[0]['id']}", headers=h)).json()
        assert lesson["exercises"]
        r = await client.post(f"/api/lesson/{lesson['lesson_id']}/complete",
                              headers=h)
        assert r.status_code == 200
        progress = (await client.get("/api/progress", headers=h)).json()
        assert progress["lessons_done_today"] == 1


@pytest.mark.asyncio
async def test_api_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/me", headers={"X-Init-Data": "bad=1&hash=x"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_free_users_limited_to_one_language():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"X-Init-Data": make_init_data(55)}
        langs = (await client.get("/api/languages", headers=h)).json()
        assert len(langs) == 2
        r = await client.post("/api/languages", headers=h,
                              json={"language_id": langs[0]["id"]})
        assert r.status_code == 200
        # второй язык без подписки — 402
        r = await client.post("/api/languages", headers=h,
                              json={"language_id": langs[1]["id"]})
        assert r.status_code == 402
        me = (await client.get("/api/me", headers=h)).json()
        assert me["can_add_language"] is False


@pytest.mark.asyncio
async def test_placement_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"X-Init-Data": make_init_data(66)}
        langs = (await client.get("/api/languages", headers=h)).json()
        await client.post("/api/languages", headers=h,
                          json={"language_id": langs[0]["id"]})
        r = await client.post("/api/placement/start", headers=h,
                              json={"language_id": langs[0]["id"], "self_level": "A2"})
        assert r.status_code == 200
        questions = r.json()["questions"]
        assert 1 <= len(questions) <= 5
        r = await client.post("/api/placement/finish", headers=h,
                              json={"language_id": langs[0]["id"], "score": 2})
        # 2/5 → уровень ниже самооценки: A2 -> A1
        assert r.json()["level"] == "A1"
        progress = (await client.get("/api/progress", headers=h)).json()
        assert progress["items"][0]["level"] == "A1"
        # урок выдаётся по уровню A1
        lesson = (await client.get(f"/api/lesson/{langs[0]['id']}", headers=h)).json()
        assert lesson["level"] == "A1"


@pytest.mark.asyncio
async def test_gap_has_single_correct_option():
    async with SessionLocal() as s:
        gaps = (await s.execute(
            select(Exercise).where(Exercise.type == "gap"))).scalars().all()
        assert len(gaps) > 50
        for ex in gaps:
            assert ex.payload["options"].count(ex.payload["correct"]) == 1
            assert "___" in ex.payload["sentence"]


@pytest.mark.asyncio
async def test_history_and_repeat():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = {"X-Init-Data": make_init_data(88)}
        langs = (await client.get("/api/languages", headers=h)).json()
        await client.post("/api/languages", headers=h,
                          json={"language_id": langs[0]["id"]})
        lesson = (await client.get(f"/api/lesson/{langs[0]['id']}", headers=h)).json()
        await client.post(f"/api/lesson/{lesson['lesson_id']}/complete", headers=h)
        hist = (await client.get("/api/history", headers=h)).json()
        assert len(hist["items"]) == 1
        assert hist["items"][0]["lesson_id"] == lesson["lesson_id"]
        # повтор: тот же урок, без проверки лимита
        rep = (await client.get(
            f"/api/repeat/{lesson['lesson_id']}", headers=h)).json()
        assert rep["repeat"] is True
        assert len(rep["exercises"]) == len(lesson["exercises"])
