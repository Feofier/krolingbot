from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import FREE_DAILY_LESSONS
from .models import (DailyActivity, Lesson, LessonCompletion, Subscription,
                     User, UserLanguage)


def msk_today() -> date:
    return (datetime.utcnow() + timedelta(hours=3)).date()


LEVELS = ["A1", "A2", "B1", "B2", "C1"]


def next_level(level: str) -> str:
    return LEVELS[min(LEVELS.index(level) + 1, len(LEVELS) - 1)] if level in LEVELS else "A1"


def prev_level(level: str) -> str:
    return LEVELS[max(LEVELS.index(level) - 1, 0)] if level in LEVELS else "A1"


async def get_or_create_user(session: AsyncSession, telegram_id: int,
                             username: str | None = None,
                             first_name: str | None = None) -> User:
    user = (await session.execute(
        select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.commit()
    return user


async def active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    res = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.expires_at > datetime.utcnow())
        .order_by(Subscription.expires_at.desc()))
    return res.scalars().first()


async def lessons_done_today(session: AsyncSession, user_id: int) -> int:
    row = (await session.execute(
        select(DailyActivity).where(
            DailyActivity.user_id == user_id, DailyActivity.day == msk_today())
    )).scalar_one_or_none()
    return row.lessons_done if row else 0


async def can_start_lesson(session: AsyncSession, user_id: int) -> bool:
    if await active_subscription(session, user_id):
        return True
    return await lessons_done_today(session, user_id) < FREE_DAILY_LESSONS


async def complete_lesson(session: AsyncSession, user: User, user_lang: UserLanguage,
                          lesson: Lesson) -> dict:
    today = msk_today()
    gift = False

    already = (await session.execute(
        select(LessonCompletion).where(
            LessonCompletion.user_id == user.id,
            LessonCompletion.lesson_id == lesson.id))).scalar_one_or_none()
    if already:
        return {"gift": False}

    activity = (await session.execute(
        select(DailyActivity).where(
            DailyActivity.user_id == user.id, DailyActivity.day == today)
    )).scalar_one_or_none()
    if activity is None:
        activity = DailyActivity(user_id=user.id, day=today, lessons_done=0)
        session.add(activity)
    activity.lessons_done += 1

    if user.last_activity_date != today:
        yesterday = today - timedelta(days=1)
        user.streak = user.streak + 1 if user.last_activity_date == yesterday else 1
        user.last_activity_date = today

    # Подарок бесплатным: каждый 3-й день стрика — +1 урок сегодня
    if user.streak > 0 and user.streak % 3 == 0:
        sub = await active_subscription(session, user.id)
        if sub is None and activity.lessons_done > 0:
            activity.lessons_done -= 1
            gift = True

    user.xp += 10
    session.add(LessonCompletion(user_id=user.id, lesson_id=lesson.id))

    next_count = (await session.execute(
        select(func.count(Lesson.id)).where(
            Lesson.language_id == user_lang.language_id,
            Lesson.level == user_lang.level,
            Lesson.number > lesson.number))).scalar_one()
    max_num = (await session.execute(
        select(func.max(Lesson.number)).where(
            Lesson.language_id == user_lang.language_id,
            Lesson.level == user_lang.level))).scalar_one()
    if next_count and lesson.number < (max_num or 0):
        user_lang.current_lesson = lesson.number + 1
    else:
        # уровень пройден — переход только через экзамен (>= 70%)
        user_lang.current_lesson = lesson.number
    session.add(user_lang)

    await session.commit()
    return {"gift": gift}


async def grant_subscription(session: AsyncSession, user_id: int, plan: str,
                             days: int) -> None:
    now = datetime.utcnow()
    sub = await active_subscription(session, user_id)
    if sub:
        sub.expires_at = max(sub.expires_at, now) + timedelta(days=days)
        session.add(sub)
    else:
        session.add(Subscription(user_id=user_id, plan=plan,
                                 expires_at=now + timedelta(days=days)))
    await session.commit()
