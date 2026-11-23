from datetime import date as date_type, datetime, timedelta

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


class MePatchIn(BaseModel):
    ui_language: str | None = None


class GameXpIn(BaseModel):
    points: int


UI_LANGUAGES = [
    {"code": "ru", "name": "Русский"},
    {"code": "en", "name": "English"},
    {"code": "es", "name": "Español"},
    {"code": "de", "name": "Deutsch"},
    {"code": "fr", "name": "Français"},
    {"code": "it", "name": "Italiano"},
    {"code": "pt", "name": "Português"},
    {"code": "tr", "name": "Türkçe"},
    {"code": "pl", "name": "Polski"},
    {"code": "uk", "name": "Українська"},
    {"code": "ja", "name": "日本語"},
    {"code": "zh", "name": "中文"},
    {"code": "ar", "name": "العربية"},
    {"code": "kk", "name": "Қазақша"},
    {"code": "uz", "name": "O'zbek"},
]


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
        "ui_language": user.ui_language or "ru",
        "lessons_done_today": await lessons_done_today(session, user.id),
        "subscription_days_left": (sub.expires_at.date() - date_type.today()).days if sub else 0,
        "has_subscription": sub is not None,
        "can_add_language": sub is not None or lang_count == 0,
        "languages_count": lang_count,
    }


@router.patch("/me")
async def patch_me(data: MePatchIn,
                   user_tg: dict = Depends(get_telegram_user),
                   session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    if data.ui_language is not None:
        user.ui_language = data.ui_language
        session.add(user)
        await session.commit()
    return {"ok": True, "ui_language": user.ui_language or "ru"}


@router.get("/ui_languages")
async def ui_languages():
    return UI_LANGUAGES


@router.get("/game/words/{language_id}")
async def game_words(language_id: int, n: int = 12,
                     user_tg: dict = Depends(get_telegram_user),
                     session: AsyncSession = Depends(get_session)):
    """Слова для мини-игр: выборка из словарей уроков языка."""
    user = await get_or_create_user(session, user_tg["id"])
    lessons = (await session.execute(
        select(Lesson).where(Lesson.language_id == language_id))).scalars().all()
    pool = []
    for lesson in lessons:
        if lesson.intro and lesson.intro.get("words"):
            pool.extend(lesson.intro["words"])
    # уникальные пары
    seen = set()
    pairs = []
    for w, t in pool:
        if w not in seen:
            seen.add(w)
            pairs.append({"word": w, "translation": t})
    import random
    rng = random.Random(user.id + language_id)
    rng.shuffle(pairs)
    return {"pairs": pairs[:n]}


@router.post("/game/xp")
async def game_xp(data: GameXpIn,
                  user_tg: dict = Depends(get_telegram_user),
                  session: AsyncSession = Depends(get_session)):
    """Начисление XP за мини-игры (не более 30 XP за один запрос)."""
    user = await get_or_create_user(session, user_tg["id"])
    points = max(0, min(data.points, 30))
    user.xp += points
    session.add(user)
    await session.commit()
    return {"ok": True, "xp": user.xp, "granted": points}


@router.get("/languages")
async def languages(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Language))).scalars().all()
    return [{"id": l.id, "code": l.code, "name": l.name, "flag": l.flag} for l in rows]


@router.post("/language/change")
async def change_language(data: LanguageIn,
                          user_tg: dict = Depends(get_telegram_user),
                          session: AsyncSession = Depends(get_session)):
    """Смена изучаемого языка: бесплатно — раз в 7 дней, с подпиской — без ограничений."""
    user = await get_or_create_user(session, user_tg["id"])
    sub = await active_subscription(session, user.id)
    if sub is None and user.last_lang_change is not None:
        elapsed = datetime.utcnow() - user.last_lang_change
        if elapsed < timedelta(days=7):
            left = 7 - elapsed.days
            raise HTTPException(
                403, f"Смена языка будет доступна через {left} дн. "
                     f"С подпиской — без ожидания.")
    lang = await session.get(Language, data.language_id)
    if not lang:
        raise HTTPException(404, "Language not found")
    ul = (await session.execute(
        select(UserLanguage).where(UserLanguage.user_id == user.id))).scalar_one_or_none()
    if ul and ul.language_id == data.language_id:
        return {"ok": True, "changed": False}
    if ul is None:
        ul = UserLanguage(user_id=user.id, language_id=data.language_id)
        session.add(ul)
    else:
        ul.language_id = data.language_id
        ul.level = "A1"
        ul.current_lesson = 1
        session.add(ul)
    user.last_lang_change = datetime.utcnow()
    session.add(user)
    await session.commit()
    return {"ok": True, "changed": True}


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
        lessons = (await session.execute(
            select(Lesson).where(
                Lesson.language_id == ul.language_id,
                Lesson.level == ul.level).order_by(Lesson.number))).scalars().all()
        done_ids = set((await session.execute(
            select(LessonCompletion.lesson_id)
            .where(LessonCompletion.user_id == user.id))).scalars().all())
        path = [{"number": l.number, "lesson_id": l.id,
                 "title": l.title, "done": l.id in done_ids} for l in lessons]
        done_count = sum(1 for p in path if p["done"])
        lang = await session.get(Language, ul.language_id)
        current = next((p for p in path if not p["done"]), None)
        result.append({
            "language_id": ul.language_id,
            "language_name": lang.name if lang else "",
            "level": ul.level,
            "level_name": LEVEL_NAMES.get(ul.level, ul.level),
            "next_level": next_level(ul.level),
            "current_lesson": current["number"] if current else ul.current_lesson,
            "lesson_title": current["title"] if current else "Время экзамена!",
            "completed": current is None,
            "level_done": done_count,
            "level_total": len(path),
            "exam_open": current is None and len(path) > 0,
            "path": path,
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
        "intro_words": lesson.intro.get("words", []) if lesson.intro else [],
        "exercises": [
            {"id": e.id, "type": e.type, "prompt": e.prompt, "payload": e.payload}
            for e in exercises
        ],
    }


class ExamFinishIn(BaseModel):
    score: int
    total: int


class MePatchIn(BaseModel):
    ui_language: str | None = None


@router.get("/exam/{language_id}")
async def exam_start(language_id: int, user_tg: dict = Depends(get_telegram_user),
                     session: AsyncSession = Depends(get_session)):
    """Экзамен на переход уровня: 20 вопросов по всем урокам текущего уровня.
    Лимит бесплатных уроков не тратит — экзамен это награда, а не урок."""
    user = await get_or_create_user(session, user_tg["id"])
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    lessons = (await session.execute(
        select(Lesson).where(
            Lesson.language_id == language_id,
            Lesson.level == ul.level).order_by(Lesson.number))).scalars().all()
    done_ids = set((await session.execute(
        select(LessonCompletion.lesson_id)
        .where(LessonCompletion.user_id == user.id))).scalars().all())
    if any(l.id not in done_ids for l in lessons):
        raise HTTPException(403, "Сначала пройди все уроки уровня")
    import random
    rng = random.Random(language_id * 1000 + user.id)
    questions = []
    for lesson in lessons:
        exs = (await session.execute(
            select(Exercise).where(
                Exercise.lesson_id == lesson.id,
                Exercise.type.in_(["choice", "gap"])))).scalars().all()
        for ex in rng.sample(exs, min(1, len(exs))):
            payload = ex.payload
            if ex.type == "gap":
                payload = {**payload,
                           "options": payload["options"] + []}
            questions.append({"type": ex.type, "prompt": ex.prompt,
                              "sentence": payload.get("sentence", ""),
                              "payload": payload})
    rng.shuffle(questions)
    return {"level": ul.level, "questions": questions[:20]}


@router.post("/exam/{language_id}/finish")
async def exam_finish(language_id: int, data: ExamFinishIn,
                      user_tg: dict = Depends(get_telegram_user),
                      session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"])
    ul = (await session.execute(
        select(UserLanguage).where(
            UserLanguage.user_id == user.id,
            UserLanguage.language_id == language_id))).scalar_one_or_none()
    if not ul:
        raise HTTPException(404, "Language not chosen")
    passed = data.total > 0 and data.score / data.total >= 0.7
    if passed:
        ul.level = next_level(ul.level)
        ul.current_lesson = 1
        session.add(ul)
        await session.commit()
    return {"passed": passed,
            "percent": round(data.score / data.total * 100) if data.total else 0,
            "level": ul.level,
            "level_name": LEVEL_NAMES.get(ul.level, ul.level)}


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
