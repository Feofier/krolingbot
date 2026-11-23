import asyncio
import json
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message,
                           PreCheckoutQuery, SuccessfulPayment)

from ..config import MINIAPP_URL, PLANS
from ..db import SessionLocal
from ..models import User
from ..services import get_or_create_user, grant_subscription, msk_today
from ..models import Payment

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        await get_or_create_user(session, message.from_user.id,
                                 message.from_user.username,
                                 message.from_user.first_name)
    await message.answer(
        "Привет! Я Krolingo — твой кенгуру-наставник в мире языков. "
        "Учимся понемногу каждый день, играем и собираем стрики. "
        "Начнём заниматься? Жми кнопку «Учить язык» в меню слева от ввода сообщения!")


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(
        "Krolingo — мини-приложение для изучения языков.\n\n"
        "Что умею:\n"
        "— Уроки по уровням A1–C1 с тестом уровня в начале\n"
        "— Грамматика и теория простым языком\n"
        "— Игры: Спринт, Анаграммы, Пары, Викторина\n"
        "— Питомец-кенгуру, который радуется твоим занятиям\n"
        "— Рейтинг учеников и стрики\n\n"
        "Команды:\n"
        "/subscribe — оформить подписку\n"
        "/about — обо мне")


def plans_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"{info['title']} — {info['stars']}⭐",
        callback_data=f"plan:{key}")]
        for key, info in PLANS.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    await message.answer(
        "Подписка Krolingo открывает:\n"
        "— безлимитные уроки каждый день\n"
        "— несколько языков сразу\n"
        "— смену языка без ожидания\n"
        "— двойной XP в играх и сундуки на пути\n\n"
        "Выбери тариф:",
        reply_markup=plans_keyboard())


@router.callback_query(F.data.startswith("plan:"))
async def plan_callback(query: CallbackQuery, bot: Bot) -> None:
    plan = query.data.split(":", 1)[1]
    info = PLANS.get(plan)
    if not info:
        await query.answer("Тариф не найден")
        return
    await query.answer()
    await bot.send_invoice(
        chat_id=query.from_user.id,
        title=info["title"],
        description=f"Безлимитные уроки на {info['days']} дней",
        payload=plan,
        currency="XTR",
        prices=[LabeledPrice(label=info["title"], amount=info["stars"])])


@router.message(F.web_app_data)
async def web_app_data(message: Message, bot: Bot) -> None:
    """Покупки из Mini App (tg.sendData)."""
    try:
        data = json.loads(message.web_app_data.data)
    except (TypeError, json.JSONDecodeError):
        return
    if data.get("action") == "buy_plan":
        plan = data.get("plan")
        info = PLANS.get(plan)
        if not info:
            return
        await bot.send_invoice(
            chat_id=message.from_user.id,
            title=info["title"],
            description=f"Безлимитные уроки на {info['days']} дней",
            payload=plan,
            currency="XTR",
            prices=[LabeledPrice(label=info["title"], amount=info["stars"])])


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=query.invoice_payload in PLANS)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment: SuccessfulPayment = message.successful_payment
    plan = payment.invoice_payload
    info = PLANS.get(plan)
    if not info:
        return
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user.id)
        await session.merge(Payment(
            user_id=user.id,
            telegram_charge_id=payment.telegram_payment_charge_id,
            plan=plan,
            stars=info["stars"]))
        await session.commit()
        await grant_subscription(session, user.id, plan, info["days"])
    await message.answer(
        f"Подписка «{info['title']}» активна. Приятного обучения!")


BOT_COMMANDS = [
    {"command": "start", "description": "Начать / открыть мини-приложение"},
    {"command": "subscribe", "description": "Оформить подписку"},
    {"command": "about", "description": "Что умеет Krolingo"},
]


def setup_dp() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


REMINDERS = [
    "Кенгу уже отсчитал все прыжки и заскучал. Хватит ему хвостом махать — один урок, и он снова счастлив!",
    "Твой стрик подаёт признаки жизни… но очень слабые. Спаси его — одним уроком!",
    "Интересный факт: ученики, которые занимаются каждый день, выучивают язык в 3 раза быстрее. Кенгу проверял.",
    "Кенгу заглянул в сумку — там пусто и как-то одиноко. Займи его делом: урок ждёт!",
    "Даже кенгуру отдыхают между прыжками. Но ты уже отдохнул — возвращайся на тропу!",
    "Твоя серия дней подряд дрожит, как хвост перед прыжком. Поймай баланс — пройди урок!",
    "Кенгу приготовил тебе место в сумке. Туда попадают только те, кто занимался сегодня!",
    "Одна маленькая урока — и день уже не зря. Кенгу верит в тебя (и в морковку).",
    "Статистика Krolingo: 100% учеников, вернувшихся сегодня, гордятся собой. Проверь!",
    "Кенгу уже помахал лапой всем соседям и некому больше махать. Вернись, ему не хватает зрителя!",
]

import random as _rng


async def reminder_loop(bot: Bot) -> None:
    """Напоминание пользователям, которые давно не занимались."""
    from sqlalchemy import select
    while True:
        try:
            today = msk_today()
            async with SessionLocal() as session:
                users = (await session.execute(select(User))).scalars().all()
                for user in users:
                    last = user.last_activity_date
                    stale = last is None or last < today - timedelta(days=1)
                    reminded = user.last_remind == today
                    if stale and not reminded:
                        try:
                            await bot.send_message(
                                user.telegram_id, _rng.choice(REMINDERS))
                            user.last_remind = today
                            session.add(user)
                        except Exception:
                            pass
                await session.commit()
        except Exception:
            pass
        await asyncio.sleep(6 * 3600)
