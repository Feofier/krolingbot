import hashlib
import hmac
import json
import os
import urllib.parse

os.environ["BOT_TOKEN"] = "test-token-123"
os.environ["DB_URL"] = "sqlite+aiosqlite:///:memory:"

import asyncio
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


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    async def run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as s:
            from app.lessons.seed import seed_if_empty
            await seed_if_empty(s)
    asyncio.run(run())
    yield


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
        assert len(langs) == 10
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
        assert len(langs) == 10
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


@pytest.mark.asyncio
async def test_gift_every_third_streak_day():
    from datetime import timedelta
    from app.services import msk_today
    async with SessionLocal() as s:
        user = await get_or_create_user(s, 99)
        user.streak = 2
        user.last_activity_date = msk_today() - timedelta(days=1)
        await s.commit()
        lang = (await s.execute(select(Language)
                                .where(Language.code == "en"))).scalar_one()
        lessons = (await s.execute(select(Lesson)
                                   .where(Lesson.language_id == lang.id,
                                          Lesson.level == "A1")
                                   .order_by(Lesson.number))).scalars().all()
        ul = UserLanguage(user_id=user.id, language_id=lang.id)
        s.add(ul)
        await s.commit()
        result = await complete_lesson(s, user, ul, lessons[0])
        assert result["gift"] is True
        assert user.streak == 3


@pytest.mark.asyncio
async def test_exam_required_for_level_up():
    async with SessionLocal() as s:
        user = await get_or_create_user(s, 123)
        lang = (await s.execute(select(Language)
                                .where(Language.code == "en"))).scalar_one()
        lessons = (await s.execute(select(Lesson)
                                   .where(Lesson.language_id == lang.id,
                                          Lesson.level == "A1")
                                   .order_by(Lesson.number))).scalars().all()
        assert len(lessons) == 35
        ul = UserLanguage(user_id=user.id, language_id=lang.id)
        s.add(ul)
        await s.commit()
        # экзамен закрыт, пока не пройдены все уроки
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            h = {"X-Init-Data": make_init_data(123)}
            r = await c.get(f"/api/exam/{lang.id}", headers=h)
            assert r.status_code == 403
        for lesson in lessons:
            await complete_lesson(s, user, ul, lesson)
        assert ul.level == "A1"  # авто-апгрейда нет
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            h = {"X-Init-Data": make_init_data(123)}
            r = await c.get(f"/api/exam/{lang.id}", headers=h)
            assert r.status_code == 200
            qs = r.json()["questions"]
            assert 10 <= len(qs) <= 20
            # сдаём на 70%+
            r = await c.post(f"/api/exam/{lang.id}/finish", headers=h,
                             json={"score": int(len(qs) * 0.75), "total": len(qs)})
            assert r.json()["passed"] is True
            assert r.json()["level"] == "A2"
            # недопуск: 50% не проходит
            r = await c.post(f"/api/exam/{lang.id}/finish", headers=h,
                             json={"score": len(qs) // 2, "total": len(qs)})
            assert r.json()["passed"] is False


@pytest.mark.asyncio
async def test_referral_reward():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        hr = {"X-Init-Data": make_init_data(900)}
        hf = {"X-Init-Data": make_init_data(901)}
        # реферер создаётся и получает код
        me = (await c.get("/api/me", headers=hr)).json()
        assert me["first_name"] is not None
        ref = (await c.get("/api/referral", headers=hr)).json()
        assert ref["link"].startswith("https://t.me/KrolingoBot?start=ref_u900")
        # друг регистрируется с referred_by
        async with SessionLocal() as s:
            referrer = await get_or_create_user(s, 900)
            friend = await get_or_create_user(s, 901)
            friend.referred_by = 900
            await s.commit()
        # друг проходит урок -> реферер получает 30 дней
        langs = (await c.get("/api/languages", headers=hf)).json()
        await c.post("/api/languages", headers=hf,
                     json={"language_id": langs[0]["id"]})
        lesson = (await c.get(f"/api/lesson/{langs[0]['id']}", headers=hf)).json()
        r = await c.post(f"/api/lesson/{lesson['lesson_id']}/complete", headers=hf)
        assert r.json()["referral"] is True
        # проверим подписку реферера
        async with SessionLocal() as s:
            from app.services import active_subscription
            referrer = await get_or_create_user(s, 900)
            sub = await active_subscription(s, referrer.id)
            assert sub is not None and sub.plan == "ref"
        # повторный урок друга не даёт вторую награду
        lesson2 = (await c.get(f"/api/lesson/{langs[0]['id']}", headers=hf)).json()
        r2 = await c.post(f"/api/lesson/{lesson2['lesson_id']}/complete", headers=hf)
        assert r2.json()["referral"] is False
        ref2 = (await c.get("/api/referral", headers=hr)).json()
        assert ref2["rewarded"] == 1 and ref2["days_earned"] == 30
