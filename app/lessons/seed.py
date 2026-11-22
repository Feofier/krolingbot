import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Exercise, Language, Lesson

LANGS = [
    {"code": "en", "name": "Английский", "flag": "🇬🇧"},
    {"code": "es", "name": "Испанский", "flag": "🇪🇸"},
]

EN_WORDS = [
    ("cat", "кот"), ("dog", "собака"), ("house", "дом"), ("water", "вода"),
    ("apple", "яблоко"), ("book", "книга"), ("friend", "друг"), ("sun", "солнце"),
    ("tree", "дерево"), ("milk", "молоко"), ("bread", "хлеб"), ("school", "школа"),
    ("time", "время"), ("hand", "рука"), ("day", "день"), ("night", "ночь"),
    ("family", "семья"), ("city", "город"), ("river", "река"), ("music", "музыка"),
    ("run", "бежать"), ("eat", "есть"), ("drink", "пить"), ("sleep", "спать"),
    ("read", "читать"), ("write", "писать"), ("big", "большой"), ("small", "маленький"),
    ("good", "хороший"), ("new", "новый"), ("old", "старый"), ("happy", "счастливый"),
    ("red", "красный"), ("blue", "синий"), ("green", "зелёный"), ("white", "белый"),
    ("one", "один"), ("two", "два"), ("three", "три"), ("today", "сегодня"),
    ("tomorrow", "завтра"), ("morning", "утро"), ("evening", "вечер"),
]

ES_WORDS = [
    ("gato", "кот"), ("perro", "собака"), ("casa", "дом"), ("agua", "вода"),
    ("manzana", "яблоко"), ("libro", "книга"), ("amigo", "друг"), ("sol", "солнце"),
    ("árbol", "дерево"), ("leche", "молоко"), ("pan", "хлеб"), ("escuela", "школа"),
    ("tiempo", "время"), ("mano", "рука"), ("día", "день"), ("noche", "ночь"),
    ("familia", "семья"), ("ciudad", "город"), ("río", "река"), ("música", "музыка"),
    ("correr", "бежать"), ("comer", "есть"), ("beber", "пить"), ("dormir", "спать"),
    ("leer", "читать"), ("escribir", "писать"), ("grande", "большой"), ("pequeño", "маленький"),
    ("bueno", "хороший"), ("nuevo", "новый"), ("viejo", "старый"), ("feliz", "счастливый"),
    ("rojo", "красный"), ("azul", "синий"), ("verde", "зелёный"), ("blanco", "белый"),
    ("uno", "один"), ("dos", "два"), ("tres", "три"), ("hoy", "сегодня"),
    ("mañana", "завтра"), ("mañana", "утро"), ("tarde", "вечер"),
]

LESSON_TITLES = ["Базовые слова", "Семья", "Еда", "Дом", "Природа", "Глаголы",
                 "Прилагательные", "Цвета", "Числа", "Время"]

# (русский источник, правильный ответ словами целевого языка)
SENTENCES = {
    "en": [
        ("Я пью воду", "I drink water"),
        ("Кот ест хлеб", "The cat eats bread"),
        ("Она читает книгу", "She reads a book"),
        ("Мы бежим домой", "We run home"),
        ("Солнце большое", "The sun is big"),
        ("Друг пишет письмо", "A friend writes a letter"),
        ("Я вижу собаку", "I see a dog"),
        ("Дети пьют молоко", "Children drink milk"),
    ],
    "es": [
        ("Я пью воду", "Yo bebo agua"),
        ("Кот ест хлеб", "El gato come pan"),
        ("Она читает книгу", "Ella lee un libro"),
        ("Мы бежим домой", "Nosotros corremos a casa"),
        ("Солнце большое", "El sol es grande"),
        ("Друг пишет письмо", "Un amigo escribe una carta"),
        ("Я вижу собаку", "Yo veo un perro"),
        ("Дети пьют молоко", "Los niños beben leche"),
    ],
}

# лишние слова для банка (отвлекающие)
DECOYS = {
    "en": ["blue", "night", "small", "music", "they", "old", "hand", "two"],
    "es": ["azul", "noche", "pequeño", "música", "ellos", "viejo", "mano", "dos"],
}


def make_exercises(words, rng, lang_code):
    exercises = []
    n = min(len(words), 10)
    for i in range(n):
        word, translation = words[i]
        distractors = rng.sample([w for w, _ in words if w != word], 3)
        exercises.append(("choice", f"Как переводится «{word}»?",
                          {"options": [translation] + [dict((w, t) for w, t in words)[d] for d in distractors],
                           "correct": translation}))
    words2 = words[10:20] if len(words) > 10 else words[:10]
    for i, (word, translation) in enumerate(words2[:5]):
        distractors = rng.sample([w for w, _ in words if w != word], 3)
        exercises.append(("gap", f"Вставь слово: I see a ___ .",
                          {"sentence": "I see a ___ .", "options": distractors + [word],
                           "correct": word}))
    pairs = rng.sample(words, min(5, len(words)))
    exercises.append(("pairs", "Соедини пары:",
                      {"pairs": [[w, t] for w, t in pairs]}))
    sentences = SENTENCES.get(lang_code, SENTENCES["en"])
    for src, correct in rng.sample(sentences, min(3, len(sentences))):
        pool = correct.split() + rng.sample(DECOYS[lang_code], 3)
        exercises.append(("sentence", f"Переведи: «{src}»",
                          {"bank": pool, "correct": correct}))
    return exercises


async def seed_if_empty(session: AsyncSession) -> None:
    count = (await session.execute(select(func.count(Language.id)))).scalar_one()
    if count:
        return

    rng = random.Random(42)
    for lang in LANGS:
        language = Language(code=lang["code"], name=lang["name"], flag=lang["flag"])
        session.add(language)
        await session.flush()
        words = EN_WORDS if lang["code"] == "en" else ES_WORDS
        for num, title in enumerate(LESSON_TITLES, start=1):
            chunk = words[(num - 1) * 4:(num - 1) * 4 + 10] or words[:10]
            lesson = Lesson(language_id=language.id, number=num,
                            title=f"{num}. {title}")
            session.add(lesson)
            await session.flush()
            for etype, prompt, payload in make_exercises(chunk, rng, lang["code"]):
                session.add(Exercise(lesson_id=lesson.id, type=etype,
                                     prompt=prompt, payload=payload))
    await session.commit()
