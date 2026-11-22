from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import FREE_DAILY_LESSONS, PLANS
from ..db import get_session
from ..models import (Exercise, Language, Lesson, LessonCompletion, User,
                     UserLanguage)
from ..services import (LEVELS, active_subscription, can_start_lesson,
                        complete_lesson, get_or_create_user,
                        lessons_done_today, msk_today, next_level, prev_level)
from .deps import get_telegram_user

router = APIRouter(prefix="/api")

LEVEL_NAMES = {"A1": "Начальный", "A2": "Базовый", "B1": "Средний",
               "B2": "Продвинутый", "C1": "Владение"}


class LanguageIn(BaseModel):
    language_id: int


class PlacementStartIn(BaseModel):
    language_id: int
    self_level: str  # A1, A2, B1


class PlacementFinishIn(BaseModel):
    language_id: int
    score: int       # верных ответов 0..5


@router.get("/me")
async def me(user_tg: dict = Depends(get_telegram_user),
             session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"],
                                    user_tg.get("username"),
                                    user_tg.get("first_name"))
    sub = await active_subscription(session, user.id)
    lang_count = (await session.execute(
        select(func.count(UserLanguage.id)).where(
            UserLanguage.user_id == user.id))).scalar_one()
    pet_mood = "happy" if user.last_activity_date == msk_today() else "sad"
    return {
        "id": user.id,
        "first_name": user.first_name,
        "xp": user.xp,
        "streak": user.streak,
        "pet_mood": pet_mood,
        "lessons_done_today": await lessons_done_today(session, user.id),
        "subscription_days_left": (sub.expires_at.date() - date_type.today()).days if sub else 0,
        "has_subscription": sub is not None,
        "can_add_language": sub is not None or lang_count == 0,
        "languages_count": lang_count,
    }


@router.get("/languages")
async def languages(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Language))).scalars().all()
    return [{"id": l.id, "code": l.code, "name": l.name, "flag": l.flag} for l in rows]


@router.post("/languages")
async def choose_language(data: LanguageIn,
                          user_tg: dict = Depends(get_telegram_user),
                          session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    exists = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == data.language_id))).scalar_one_or_none()
    if exists:
        return {"ok": True}
    lang = await session.get(Language, data.language_id)
    if not lang:
        raise HTTPException(404, "Language not found")
    sub = await active_subscription(session, user.id)
    count = (await session.execute(
        select(func.count(UserLanguage.id)).where(
            UserLanguage.user_id == user.id))).scalar_one()
    if count >= 1 and sub is None:
        raise HTTPException(402, "Бесплатно доступен 1 язык. Оформи подписку, чтобы добавить ещё.")
    session.add(UserLanguage(user_id=user.id, language_id=data.language_id))
    await session.commit()
    return {"ok": True}


@router.get("/progress")
async def progress(user_tg: dict = Depends(get_telegram_user),
                   session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    rows = (await session.execute(
        select(UserLanguage).where(UserLanguage.user_id == user.id))).scalars().all()
    result = []
    for ul in rows:
        lesson = (await session.execute(
            select(Lesson).where(
                Lesson.language_id == ul.language_id,
                Lesson.level == ul.level,
                Lesson.number == ul.current_lesson))).scalar_one_or_none()
        lang = await session.get(Language, ul.language_id)
        result.append({
            "language_id": ul.language_id,
            "language_name": lang.name if lang else "",
            "level": ul.level,
            "level_name": LEVEL_NAMES.get(ul.level, ul.level),
            "current_lesson": ul.current_lesson,
            "lesson_title": lesson.title if lesson else "Всё пройдено!",
            "completed": lesson is None,
        })
    done_today = await lessons_done_today(session, user.id)
    return {
        "items": result,
        "lessons_done_today": done_today,
        "free_daily_limit": FREE_DAILY_LESSONS,
        "can_start": await can_start_lesson(session, user.id),
    }


@router.get("/lesson/{language_id}")
async def get_lesson(language_id: int, user_tg: dict = Depends(get_telegram_user),
                     session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    if not await can_start_lesson(session, user.id):
        raise HTTPException(402, "Daily limit reached. Subscription required.")
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    lesson = (await session.execute(
        select(Lesson).where(
            Lesson.language_id == language_id,
            Lesson.level == ul.level,
            Lesson.number == ul.current_lesson))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, "All lessons completed")
    exercises = (await session.execute(
        select(Exercise).where(Exercise.lesson_id == lesson.id))).scalars().all()
    return {
        "lesson_id": lesson.id,
        "number": lesson.number,
        "level": lesson.level,
        "title": f"{lesson.title}",
        "exercises": [
            {"id": e.id, "type": e.type, "prompt": e.prompt, "payload": e.payload}
            for e in exercises
        ],
    }


@router.post("/lesson/{lesson_id}/complete")
async def finish_lesson(lesson_id: int, user_tg: dict = Depends(get_telegram_user),
                        session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    lesson = await session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == lesson.language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    result = await complete_lesson(session, user, ul, lesson)
    return {"ok": True, "xp": user.xp, "streak": user.streak,
            "level": ul.level, "current_lesson": ul.current_lesson,
            "gift": result.get("gift", False)}


@router.post("/placement/start")
async def placement_start(data: PlacementStartIn,
                          user_tg: dict = Depends(get_telegram_user),
                          session: AsyncSession = Depends(get_session)):
    """Возвращает 5 тестовых заданий по самооценённому уровню."""
    if data.self_level not in LEVELS:
        raise HTTPException(400, "Unknown level")
    user = await get_or_create_user(session, user_tg["id"])
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == data.language_id))).scalar_one_or_none()
    if ul:
        ul.level = data.self_level  # фиксируем самооценку до теста
        session.add(ul)
        await session.commit()
    lessons = (await session.execute(
        select(Lesson).where(
            Lesson.language_id == data.language_id,
            Lesson.level == data.self_level))).scalars().all()
    if not lessons:
        raise HTTPException(404, "No lessons for level")
    import random
    rng = random.Random(data.language_id)
    picked = rng.sample(lessons, min(5, len(lessons)))
    questions = []
    for lesson in picked:
        ex = (await session.execute(
            select(Exercise).where(
                Exercise.lesson_id == lesson.id,
                Exercise.type == "choice"))).scalars().first()
        if ex:
            questions.append({"type": ex.type, "prompt": ex.prompt,
                              "payload": ex.payload})
    return {"questions": questions[:5]}


@router.post("/placement/finish")
async def placement_finish(data: PlacementFinishIn,
                           user_tg: dict = Depends(get_telegram_user),
                           session: AsyncSession = Depends(get_session)):
    """Сохраняет итоговый уровень: 0-2 → уровень ниже, 3-4 → как есть, 5 → выше."""
    user = await get_or_create_user(session, user_tg["id"])
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == data.language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    self_level = ul.level if ul.level else "A1"
    if data.score <= 2:
        level = prev_level(self_level)
    elif data.score >= 5:
        level = next_level(self_level)
    else:
        level = self_level
    ul.level = level
    ul.current_lesson = 1
    session.add(ul)
    await session.commit()
    return {"level": level, "level_name": LEVEL_NAMES.get(level, level)}


@router.get("/plans")
async def plans():
    return [{"key": k, **v} for k, v in PLANS.items()]


@router.get("/history")
async def history(user_tg: dict = Depends(get_telegram_user),
                  session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    rows = (await session.execute(
        select(LessonCompletion, Lesson, Language)
        .join(Lesson, Lesson.id == LessonCompletion.lesson_id)
        .join(Language, Language.id == Lesson.language_id)
        .where(LessonCompletion.user_id == user.id)
        .order_by(LessonCompletion.completed_at.desc())
        .limit(30))).all()
    items = []
    for comp, lesson, lang in rows:
        items.append({
            "lesson_id": lesson.id,
            "title": lesson.title,
            "level": lesson.level,
            "language_name": lang.name,
            "completed_at": comp.completed_at.strftime("%d.%m.%Y"),
        })
    return {"items": items}


@router.get("/repeat/{lesson_id}")
async def repeat_lesson(lesson_id: int,
                        user_tg: dict = Depends(get_telegram_user),
                        session: AsyncSession = Depends(get_session)):
    """Урок для повторения: без проверки лимита, не двигает прогресс."""
    user = await get_or_create_user(session, user_tg["id"])
    lesson = await session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == lesson.language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    exercises = (await session.execute(
        select(Exercise).where(Exercise.lesson_id == lesson.id))).scalars().all()
    return {
        "lesson_id": lesson.id,
        "number": lesson.number,
        "level": lesson.level,
        "title": f"Повторение · {lesson.title}",
        "repeat": True,
        "exercises": [
            {"id": e.id, "type": e.type, "prompt": e.prompt, "payload": e.payload}
            for e in exercises
        ],
    }


@router.get("/leaderboard")
async def leaderboard(user_tg: dict = Depends(get_telegram_user),
                      session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    rows = (await session.execute(
        select(User).order_by(User.xp.desc()).limit(20))).scalars().all()
    items = []
    for i, u in enumerate(rows, start=1):
        items.append({
            "rank": i,
            "name": u.first_name or (u.username or f"User {u.telegram_id}"),
            "xp": u.xp,
            "is_me": u.id == user.id,
        })
    my_rank = next((i["rank"] for i in items if i["is_me"]), None)
    if my_rank is None:
        better = (await session.execute(
            select(func.count(User.id)).where(User.xp > user.xp))).scalar_one()
        my_rank = better + 1
    return {"items": items, "my_rank": my_rank, "my_xp": user.xp}
