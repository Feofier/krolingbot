from datetime import date, datetime

from sqlalchemy import (JSON, Date, DateTime, ForeignKey, Integer, BigInteger,
                        String, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    languages: Mapped[list["UserLanguage"]] = relationship(back_populates="user",
                                                           cascade="all, delete-orphan")


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)  # en, es
    name: Mapped[str] = mapped_column(String(64))  # Английский
    flag: Mapped[str] = mapped_column(String(8), default="")


class UserLanguage(Base):
    __tablename__ = "user_languages"
    __table_args__ = (UniqueConstraint("user_id", "language_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"))
    current_lesson: Mapped[int] = mapped_column(Integer, default=1)  # следующий урок
    level: Mapped[str] = mapped_column(String(4), default="A1")  # A1, A2, B1

    user: Mapped[User] = relationship(back_populates="languages")
    language: Mapped[Language] = relationship()


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"), index=True)
    level: Mapped[str] = mapped_column(String(4), default="A1")
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    intro: Mapped[dict] = mapped_column(JSON, default=dict)
    # intro: {"words": [["cat","кот"], ...]} — слова для экрана знакомства

    language: Mapped[Language] = relationship()


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # choice, gap, pairs
    prompt: Mapped[str] = mapped_column(String(512))
    payload: Mapped[dict] = mapped_column(JSON)
    # choice: {"options": [...], "correct": "..."}
    # gap:    {"sentence": "...", "options": [...], "correct": "..."}
    # pairs:  {"pairs": [["cat","кот"], ...]}


class LessonCompletion(Base):
    __tablename__ = "lesson_completions"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    completed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DailyActivity(Base):
    __tablename__ = "daily_activities"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    lessons_done: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(16))  # week, month, halfyear
    starts_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    telegram_charge_id: Mapped[str] = mapped_column(String(64), unique=True)
    plan: Mapped[str] = mapped_column(String(16))
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
