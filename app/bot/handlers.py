from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (KeyboardButton, LabeledPrice, Message,
                           PreCheckoutQuery, ReplyKeyboardMarkup,
                           SuccessfulPayment)

from ..config import MINIAPP_URL, PLANS
from ..db import SessionLocal
from ..services import get_or_create_user, grant_subscription
from ..models import Payment

router = Router()


def miniapp_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Открыть приложение", web_app={"url": MINIAPP_URL})]],
        resize_keyboard=True)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        await get_or_create_user(session, message.from_user.id,
                                 message.from_user.username,
                                 message.from_user.first_name)
    await message.answer(
        "Привет! Это Krolingo — учи языки по 5 минут в день. "
        "Бесплатно доступно 2 урока в день.",
        reply_markup=miniapp_keyboard())


@router.message(F.text.in_({p["title"] for p in PLANS.values()}))
async def buy_plan(message: Message, bot: Bot) -> None:
    plan = next(k for k, v in PLANS.items() if v["title"] == message.text)
    info = PLANS[plan]
    await bot.send_invoice(
        chat_id=message.from_user.id,
        title=info["title"],
        description=f"Безлимитные уроки на {info['days']} дней",
        payload=plan,
        currency="XTR",
        prices=[LabeledPrice(label=info["title"], amount=info["stars"])],
    )


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
        f"Подписка «{info['title']}» активна. Приятного обучения!",
        reply_markup=miniapp_keyboard())


def setup_dp() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
