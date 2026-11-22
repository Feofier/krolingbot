from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import FREE_DAILY_LESSONS, PLANS
from ..db import get_session
from ..models import (Exercise, Language, Lesson, User, UserLanguage)
from ..services import (active_subscription, can_start_lesson,
                        complete_lesson, get_or_create_user,
                        lessons_done_today)
from .deps import get_telegram_user

router = APIRouter(prefix="/api")


class LanguageIn(BaseModel):
    language_id: int


@router.get("/me")
async def me(user_tg: dict = Depends(get_telegram_user),
             session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, user_tg["id"],
                                    user_tg.get("username"),
                                    user_tg.get("first_name"))
    sub = await active_subscription(session, user.id)
    return {
        "id": user.id,
        "first_name": user.first_name,
        "xp": user.xp,
        "streak": user.streak,
        "subscription_days_left": (sub.expires_at.date() - date_type.today()).days if sub else 0,
        "has_subscription": sub is not None,
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
    if not exists:
        lang = await session.get(Language, data.language_id)
        if not lang:
            raise HTTPException(404, "Language not found")
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
                Lesson.number == ul.current_lesson))).scalar_one_or_none()
        result.append({
            "language_id": ul.language_id,
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
            Lesson.number == ul.current_lesson))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, "All lessons completed")
    exercises = (await session.execute(
        select(Exercise).where(Exercise.lesson_id == lesson.id))).scalars().all()
    return {
        "lesson_id": lesson.id,
        "number": lesson.number,
        "title": lesson.title,
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
    await complete_lesson(session, user, ul, lesson)
    return {"ok": True, "xp": user.xp, "streak": user.streak}


@router.get("/plans")
async def plans():
    return [{"key": k, **v} for k, v in PLANS.items()]
